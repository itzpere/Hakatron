#!/usr/bin/env python3
"""
Raspberry Pi Climate Controller – AUTO / LOW / MANUAL
====================================================

Režimi
------
* **AUTO**  (switch 1 = zatvoren, switch 2 = zatvoren)
  * Brzina 1 ⇢ 25 % AC‑a  (|ΔT| ≤ 2 °C)
  * Brzina 2 ⇢ 60 % AC‑a  (2 < |ΔT| ≤ 5 °C)
  * Brzina 3 ⇢ 100 % AC‑a  (|ΔT| > 5 °C)
* **LOW**   (switch 1 = otvoren, switch 2 = zatvoren) → Brzina 1 @ 10 % AC‑a
* **OFF / WINDOW** (switch 2 = otvoren)                → Brzina 0, LED‑ovi ugašeni
* **MANUAL** (iz SCADA‑e: field `manual_speed` = 1|2|3)
  → Ignoriše temperaturu i prekidače; koristi zadatu brzinu i fiksni %.

SCADA podešavanja (Influx CLI primer)
-------------------------------------
```bash
# Ciljna T = 22 °C
influx -database mydb -execute "INSERT config target_temp=22"

# MANUAL režim, brzina 2
influx -database mydb -execute "INSERT config manual_speed=2"

# Vraćanje u AUTO (manual off)
influx -database mydb -execute "INSERT config manual_speed=0"
```

"""
from __future__ import annotations
import glob, os, time
from dataclasses import dataclass
import RPi.GPIO as GPIO
from influxdb import InfluxDBClient

# ───────── pinout & konstante ─────────────────────────────────────────
PIN_SW1, PIN_SW2 = 23, 24
PIN_LED1, PIN_LED2, PIN_LED3 = 17, 27, 22
PWM_FREQ = 1000  # Hz

DEFAULT_TARGET      = 22.0   # °C
DEFAULT_MANUAL_SPEED = 0     # 0 = off / AUTO
LOG_INTERVAL        = 5.0    # s

SPEED_TO_AC = {1: 25.0, 2: 60.0, 3: 100.0}
LOW_AC      = 10.0

INFLUX = {
    'host': 'localhost', 'port': 8086,
    'username': 'admin', 'password': 'mia',
    'database': 'mydb',  'measurement': 'environment',
}

# ───────── DS18B20 helperi ────────────────────────────────────────────

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

# ───────── GPIO / PWM setup ──────────────────────────────────────────

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup([PIN_SW1, PIN_SW2], GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup([PIN_LED1, PIN_LED2, PIN_LED3], GPIO.OUT, initial=GPIO.LOW)
    p1 = GPIO.PWM(PIN_LED1, PWM_FREQ); p1.start(0)
    p2 = GPIO.PWM(PIN_LED2, PWM_FREQ); p2.start(0)
    p3 = GPIO.PWM(PIN_LED3, PWM_FREQ); p3.start(0)
    return p1, p2, p3

# ───────── data strukture ────────────────────────────────────────────
@dataclass
class SwitchState:
    auto_mode: bool      # True = normal, False = LOW
    window_open: bool

@dataclass
class ClimateCommand:
    fan_speed: int       # 0–3
    ac_intensity: float  # % 0‑100

# ───────── logika ────────────────────────────────────────────────────

def read_switches() -> SwitchState:
    return SwitchState(GPIO.input(PIN_SW1)==GPIO.LOW,   # LOW = pulled to GND → switch closed
                       GPIO.input(PIN_SW2)==GPIO.LOW)


def compute_command(temp: float, tgt: float, sw: SwitchState, manual_speed: int) -> ClimateCommand:
    # MANUAL – najviši prioritet
    if manual_speed in (1, 2, 3):
        return ClimateCommand(manual_speed, SPEED_TO_AC[manual_speed])

    # WINDOW / OFF
    if sw.window_open:
        return ClimateCommand(0, 0.0)

    # LOW režim
    if not sw.auto_mode:   # switch1 open → LOW
        return ClimateCommand(1, LOW_AC)

    # AUTO
    delta = abs(temp - tgt)
    if delta <= 2:
        speed = 1
    elif delta <= 5:
        speed = 2
    else:
        speed = 3
    return ClimateCommand(speed, SPEED_TO_AC[speed])


def update_leds(speed: int, pwms):
    p1, p2, p3 = pwms
    p1.ChangeDutyCycle(0); p2.ChangeDutyCycle(0); p3.ChangeDutyCycle(0)
    if speed == 1:
        p1.ChangeDutyCycle(100)
    elif speed == 2:
        p2.ChangeDutyCycle(100)
    elif speed == 3:
        p3.ChangeDutyCycle(100)
    # speed 0 → sve ugašeno

# ───────── Influx helpers ────────────────────────────────────────────

def influx_client():
    return InfluxDBClient(host=INFLUX['host'], port=INFLUX['port'],
                          username=INFLUX['username'], password=INFLUX['password'],
                          database=INFLUX['database'])


def fetch_config(cli, target: float, manual: int):
    # target_temp
    try:
        res = cli.query('SELECT LAST(target_temp) FROM config')
        if res:
            val = list(res.get_points())[0]['last']
            if val is not None:
                target = float(val)
    except Exception:
        pass
    # manual_speed
    try:
        res = cli.query('SELECT LAST(manual_speed) FROM config')
        if res:
            val = list(res.get_points())[0]['last']
            if val is not None:
                manual = int(val)
    except Exception:
        pass
    return target, manual


def log_point(cli, temp, cmd, sw, manual_speed):
    cli.write_points([{ 'measurement': INFLUX['measurement'], 'fields': {
        'sensors_temp': temp,
        'fan_speed': cmd.fan_speed,
        'ac_intensity': cmd.ac_intensity,
        'auto_mode': int(sw.auto_mode),
        'window_open': int(sw.window_open),
        'manual_speed': manual_speed,
    }}])

# ───────── main petlja ───────────────────────────────────────────────

def main():
    sensor = setup_sensor()
    pwms   = setup_gpio()
    cli    = influx_client()
    target = DEFAULT_TARGET
    manual = DEFAULT_MANUAL_SPEED
    print('Controller running… Ctrl‑C to exit')
    try:
        while True:
            target, manual = fetch_config(cli, target, manual)
            t = read_temp(sensor)
            if t is None:
                time.sleep(LOG_INTERVAL); continue
            sw  = read_switches()
            cmd = compute_command(t, target, sw, manual)
            update_leds(cmd.fan_speed, pwms)
            log_point(cli, t, cmd, sw, manual)

            # status string
            if manual in (1, 2, 3):
                mode = f'MANUAL-{manual}'
            else:
                if sw.window_open:
                    mode = 'OFF'
                elif not sw.auto_mode:
                    mode = 'LOW'
                else:
                    mode = 'AUTO'
            print(f"{time.strftime('%H:%M:%S')}  T={t:5.2f}°C  Set={target:.2f}°C  {mode:<7}  FAN={cmd.fan_speed}  AC={cmd.ac_intensity:5.1f}%")
            time.sleep(LOG_INTERVAL)
    except KeyboardInterrupt:
        print('\nBye')
    finally:
        for p in pwms: p.stop(); GPIO.cleanup()

if __name__ == '__main__':
    main()
