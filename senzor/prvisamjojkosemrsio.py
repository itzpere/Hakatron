#!/usr/bin/env python3
"""
Unified Raspberry Pi Climate Controller
=======================================

This script combines the functionalities of AUTO, LOW, MANUAL, and PID modes.
Users can select the desired mode at runtime.

Modes:
------
* **AUTO**: Automatically adjusts fan speed based on temperature difference.
* **LOW**: Fixed low-speed operation.
* **MANUAL**: User-defined fan speed.
* **PID**: PID-controlled fan-coil drive.

"""
from __future__ import annotations
import glob, os, time
from dataclasses import dataclass
import RPi.GPIO as GPIO
from influxdb import InfluxDBClient

# ───────── pinout & constants ───────────────────────────────────────
PIN_SW1, PIN_SW2 = 23, 24
PIN_LED1, PIN_LED2, PIN_LED3 = 17, 27, 22
PWM_FREQ = 1000  # Hz

DEFAULT_TARGET = 22.0  # °C
LOG_INTERVAL = 5.0  # s
PID_RESET_INTERVAL = 10.0  # s

DEFAULT_PID = {'kp': 8.0, 'ki': 0.20, 'kd': 1.0}

SPEED_TO_AC = {1: 25.0, 2: 60.0, 3: 100.0}
LOW_AC = 10.0

INFLUX = {
    'host': 'localhost', 'port': 8086,
    'username': 'admin', 'password': 'mia',
    'database': 'mydb',  'measurement': 'environment',
}

# ───────── DS18B20 helpers ──────────────────────────────────────────

def setup_sensor() -> str:
    os.system('modprobe w1-gpio')
    os.system('modprobe w1-therm')
    dev = glob.glob('/sys/bus/w1/devices/28*')
    if not dev:
        raise RuntimeError('DS18B20 not found')
    return dev[0] + '/w1_slave'

def read_temp(file: str) -> float | None:
    with open(file) as f:
        lines = f.readlines()
    if lines[0].strip()[-3:] != 'YES':
        return None
    return float(lines[1].split('t=')[1]) / 1000.0

# ───────── GPIO / PWM setup ─────────────────────────────────────────

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup([PIN_SW1, PIN_SW2], GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup([PIN_LED1, PIN_LED2, PIN_LED3], GPIO.OUT, initial=GPIO.LOW)
    p1 = GPIO.PWM(PIN_LED1, PWM_FREQ); p1.start(0)
    p2 = GPIO.PWM(PIN_LED2, PWM_FREQ); p2.start(0)
    p3 = GPIO.PWM(PIN_LED3, PWM_FREQ); p3.start(0)
    return p1, p2, p3

# ───────── data structures ──────────────────────────────────────────
@dataclass
class SwitchState:
    auto_mode: bool      # True = AUTO, False = LOW
    window_open: bool

@dataclass
class ClimateCommand:
    fan_speed: int       # 0–3
    ac_intensity: float  # % 0‑100

@dataclass
class PIDParams:
    kp: float; ki: float; kd: float

# ───────── logic / PID ─────────────────────────────────────────────

def read_switches() -> SwitchState:
    return SwitchState(GPIO.input(PIN_SW1) == GPIO.LOW,
                       GPIO.input(PIN_SW2) == GPIO.LOW)

def pid_step(error: float, dt: float, p: PIDParams,
             integral: float, prev_error: float) -> tuple[float, float, float]:
    integral += error * dt
    deriv = (error - prev_error) / dt if dt > 0 else 0.0
    out = p.kp * error + p.ki * integral + p.kd * deriv
    return max(0.0, min(100.0, out)), integral, error

def compute_command(temp: float, tgt: float, sw: SwitchState, manual_speed: int, pid_out: float) -> ClimateCommand:
    if manual_speed in (1, 2, 3):
        return ClimateCommand(manual_speed, SPEED_TO_AC[manual_speed])
    if sw.window_open:
        return ClimateCommand(0, 0.0)
    if not sw.auto_mode:
        return ClimateCommand(1, LOW_AC)
    delta = abs(temp - tgt)
    if pid_out is not None:
        speed = 1 if pid_out < 40 else 2 if pid_out < 70 else 3
        return ClimateCommand(speed, pid_out)
    if delta <= 2:
        return ClimateCommand(1, SPEED_TO_AC[1])
    elif delta <= 5:
        return ClimateCommand(2, SPEED_TO_AC[2])
    else:
        return ClimateCommand(3, SPEED_TO_AC[3])

# ───────── LED helpers ─────────────────────────────────────────────

def update_leds(speed: int, pwms):
    p1, p2, p3 = pwms
    p1.ChangeDutyCycle(0); p2.ChangeDutyCycle(0); p3.ChangeDutyCycle(0)
    if speed == 1:
        p1.ChangeDutyCycle(100)
    elif speed == 2:
        p2.ChangeDutyCycle(100)
    elif speed == 3:
        p3.ChangeDutyCycle(100)

# ───────── Influx helpers ──────────────────────────────────────────

def influx_client():
    return InfluxDBClient(**{k: INFLUX[k]
                             for k in ('host', 'port', 'username', 'password', 'database')})

def fetch_config(cli, target: float, manual: int, pid_p: PIDParams) -> tuple[float, int, PIDParams]:
    try:
        res = cli.query('SELECT LAST(target_temp) FROM config')
        if res:
            target = float(list(res.get_points())[0]['last'])
    except Exception:
        pass
    try:
        res = cli.query('SELECT LAST(manual_speed) FROM config')
        if res:
            manual = int(list(res.get_points())[0]['last'])
    except Exception:
        pass
    try:
        pid_p = PIDParams(
            kp=float(list(cli.query('SELECT LAST(kp) FROM config').get_points())[0]['last']),
            ki=float(list(cli.query('SELECT LAST(ki) FROM config').get_points())[0]['last']),
            kd=float(list(cli.query('SELECT LAST(kd) FROM config').get_points())[0]['last'])
        )
    except Exception:
        pass
    return target, manual, pid_p

def log_point(cli, temp, cmd, sw, pid_out):
    cli.write_points([{'measurement': INFLUX['measurement'], 'fields': {
        'sensors_temp': temp,
        'fan_speed': cmd.fan_speed,
        'ac_intensity': cmd.ac_intensity,
        'auto_mode': int(sw.auto_mode),
        'window_open': int(sw.window_open),
        'pid_output': pid_out,
    }}])

# ───────── main loop ───────────────────────────────────────────────

def main():
    sensor = setup_sensor()
    pwms = setup_gpio()
    cli = influx_client()

    target = DEFAULT_TARGET
    manual = 0
    pid_p = PIDParams(**DEFAULT_PID)

    integral = 0.0
    prev_error = 0.0
    last_loop = time.time()
    next_pid_reset = last_loop + PID_RESET_INTERVAL

    print('Unified Climate Controller running… Ctrl-C to exit')
    try:
        while True:
            now = time.time()
            dt = now - last_loop
            last_loop = now

            if now >= next_pid_reset:
                integral, prev_error = 0.0, 0.0
                next_pid_reset += PID_RESET_INTERVAL

            target, manual, pid_p = fetch_config(cli, target, manual, pid_p)

            temp = read_temp(sensor)
            if temp is None:
                time.sleep(LOG_INTERVAL); continue

            delta = abs(temp - target)
            pid_out, integral, prev_error = pid_step(delta, dt, pid_p, integral, prev_error)

            sw = read_switches()
            cmd = compute_command(temp, target, sw, manual, pid_out)

            update_leds(cmd.fan_speed, pwms)
            log_point(cli, temp, cmd, sw, pid_out)

            mode = ('WINDOW' if sw.window_open else
                    'AUTO' if sw.auto_mode else 'LOW')
            print(f"{time.strftime('%H:%M:%S')}  "
                  f"T={temp:5.2f}°C  Set={target:.2f}°C  "
                  f"{mode:<6}  FAN={cmd.fan_speed}  "
                  f"AC={cmd.ac_intensity:5.1f}%  "
                  f"PID({pid_p.kp:.2f},{pid_p.ki:.2f},{pid_p.kd:.2f})")

            time.sleep(LOG_INTERVAL)

    except KeyboardInterrupt:
        print('\nBye')
    finally:
        for p in pwms: p.stop()
        GPIO.cleanup()

if __name__ == '__main__':
    main()
