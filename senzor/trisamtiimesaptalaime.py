#!/usr/bin/env python3
"""
Raspberry Pi Climate Controller — SCADA target + PID fan-coil drive
==================================================================

Нова функционалност
-------------------
* **PID reset на сваких 10 s** – интеграл и претходна грешка се бришу
  (ефикасно „рестартујући“ деловање регулатора).
* **LED-индикација у AUTO-режиму** – светли тачно онај LED који
  одговара тренутној брзини вентилатора (1 = LED1, 2 = LED2, 3 = LED3).
* **LOW-режим** – као раније: 1. брзина @ 10 % AC и сија само LED1 (10 % PWM).
* **OFF-режим** – прозор отворен: вентилатор = 0 и сви LED-ови угашени.

Остало (SCADA подесиви target и PID параметри, логовање у Influx) остаје исто.
"""

from __future__ import annotations
import glob, os, time
from dataclasses import dataclass
import RPi.GPIO as GPIO
from influxdb import InfluxDBClient

# ───────── pin-out & константе ───────────────────────────────────────
PIN_SW1, PIN_SW2           = 23, 24
PIN_LED1, PIN_LED2, PIN_LED3 = 17, 27, 22
PWM_FREQ                   = 1000           # Hz

DEFAULT_TARGET             = 25.0           # °C
LOG_INTERVAL               = 5.0            # s
PID_RESET_INTERVAL         = 10.0           # s  ← NEW

DEFAULT_PID = {'kp': 8.0, 'ki': 0.20, 'kd': 1.0}

INFLUX = {
    'host': 'localhost', 'port': 8086,
    'username': 'admin', 'password': 'mia',
    'database': 'mydb',  'measurement': 'environment',
}

# ───────── DS18B20 helper-и ──────────────────────────────────────────
def setup_sensor() -> str:
    os.system('modprobe w1-gpio')
    os.system('modprobe w1-therm')
    dev = glob.glob('/sys/bus/w1/devices/28*')
    if not dev:
        raise RuntimeError('DS18B20 not found')
    return dev[0] + '/w1_slave'

def read_temp(devfile: str) -> float | None:
    with open(devfile) as f:
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

# ───────── data структуре ───────────────────────────────────────────
@dataclass
class SwitchState:
    auto_mode: bool     # SW1 closed → AUTO; open → LOW (SAVE)
    window_open: bool   # SW2 closed → OK; open → OFF

@dataclass
class ClimateCommand:
    fan_speed: int      # 0–3
    ac_intensity: float # 0–100 %

@dataclass
class PIDParams:
    kp: float; ki: float; kd: float

# ───────── логика / PID ─────────────────────────────────────────────
def read_switches() -> SwitchState:
    return SwitchState(GPIO.input(PIN_SW1) == GPIO.LOW,
                       GPIO.input(PIN_SW2) == GPIO.LOW)

def pid_step(error: float, dt: float, p: PIDParams,
             integral: float, prev_error: float) -> tuple[float, float, float]:
    integral += error * dt
    deriv = (error - prev_error) / dt if dt > 0 else 0.0
    out = p.kp * error + p.ki * integral + p.kd * deriv
    return max(0.0, min(100.0, out)), integral, error

def compute_command(delta: float, sw: SwitchState, ac_val: float) -> ClimateCommand:
    if sw.window_open:                              # OFF
        return ClimateCommand(0, 0.0)
    if sw.auto_mode:                                # AUTO
        speed = 1 if ac_val < 40 else 2 if ac_val < 70 else 3
        return ClimateCommand(speed, ac_val)
    return ClimateCommand(1, 10.0)                  # LOW

# ───────── LED helper-и ─────────────────────────────────────────────
def leds_off(pwms):
    for p in pwms: p.ChangeDutyCycle(0)

def show_low_mode(pwms, duty: float = 10.0):
    p1, p2, p3 = pwms
    p1.ChangeDutyCycle(duty); p2.ChangeDutyCycle(0); p3.ChangeDutyCycle(0)

def show_auto_mode(pwms, fan_speed: int):
    p1, p2, p3 = pwms
    p1.ChangeDutyCycle(100 if fan_speed == 1 else 0)
    p2.ChangeDutyCycle(100 if fan_speed == 2 else 0)
    p3.ChangeDutyCycle(100 if fan_speed == 3 else 0)

# ───────── Influx helpers ───────────────────────────────────────────
def influx_client():
    return InfluxDBClient(**{k: INFLUX[k]
                             for k in ('host', 'port', 'username', 'password', 'database')})

def fetch_target(cli, cur: float) -> float:
    try:
        res = cli.query('SELECT LAST(target_temp) FROM config')
        if res:
            return float(list(res.get_points())[0]['last'])
    except Exception:
        pass
    return cur

def fetch_pid_params(cli, p: PIDParams) -> PIDParams:
    def _latest(field, cur):
        try:
            r = cli.query(f'SELECT LAST({field}) FROM config')
            if r:
                return float(list(r.get_points())[0]['last'])
        except Exception:
            pass
        return cur
    return PIDParams(_latest('kp', p.kp),
                     _latest('ki', p.ki),
                     _latest('kd', p.kd))

def log_point(cli, temp, cmd, sw, target, mode):
    cli.write_points([{'measurement': INFLUX['measurement'], 'fields': {
        'sensors_temp': temp,
        'fan_speed': cmd.fan_speed,
        'ac_intensity': cmd.ac_intensity,
        'auto_mode': int(sw.auto_mode),
        'window_open': int(sw.window_open),
        'target_temp': target,
        'mode': mode,
    }}])

# ───────── главна петља ─────────────────────────────────────────────
def main():
    sensor = setup_sensor()
    pwms   = setup_gpio()
    cli    = influx_client()

    target = DEFAULT_TARGET
    pid_p  = PIDParams(**DEFAULT_PID)

    integral = 0.0
    prev_error = 0.0
    last_loop  = time.time()
    next_pid_reset = last_loop + PID_RESET_INTERVAL   # ← NEW

    print('Controller running… Ctrl-C to exit')
    try:
        while True:
            now = time.time()
            dt  = now - last_loop
            last_loop = now

            # PID reset сваких 10 s
            if now >= next_pid_reset:
                integral, prev_error = 0.0, 0.0
                next_pid_reset += PID_RESET_INTERVAL

            target = fetch_target(cli, target)
            pid_p  = fetch_pid_params(cli, pid_p)

            temp = read_temp(sensor)
            if temp is None:
                time.sleep(LOG_INTERVAL); continue

            delta = abs(temp - target)
            pid_out, integral, prev_error = pid_step(delta, dt, pid_p,
                                                     integral, prev_error)

            sw  = read_switches()
            cmd = compute_command(delta, sw, pid_out)

            # LED-индикација
            if cmd.fan_speed == 0:          # OFF
                leds_off(pwms)
            elif not sw.auto_mode:          # LOW
                show_low_mode(pwms)
            else:                           # AUTO
                show_auto_mode(pwms, cmd.fan_speed)

            mode = ('WINDOW' if sw.window_open else
                    'AUTO'   if sw.auto_mode  else 'LOW')
            log_point(cli, temp, cmd, sw, target, mode)

            print(f"{time.strftime('%H:%M:%S')}  "
                  f"T={temp:5.2f}°C  Set={target:.2f}°C  "
                  f"{mode:<6}  FAN={cmd.fan_speed}  "
                  f"AC={cmd.ac_intensity:5.1f}%  "
                  f"PID({pid_p.kp:.2f},{pid_p.ki:.2f},{pid_p.kd:.2f})")

            time.sleep(LOG_INTERVAL)

    except KeyboardInterrupt:
        print('\nBye')
    finally:
        leds_off(pwms)
        for p in pwms: p.stop()
        GPIO.cleanup()

if __name__ == '__main__':
    main()
