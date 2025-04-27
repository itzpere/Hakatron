#!/usr/bin/env python3
"""
Raspberry Pi Climate Controller – tri brzine sa fiksnim % i Low režim
====================================================================

Funkcionalnost
--------------
* **Tri automatske brzine** određene odstupanjem od ciljne T (22 °C po difoltu):
  * **Brzina 1** (|ΔT| ≤ 2 °C)  → **25 %** AC‑a, pali se LED1.
  * **Brzina 2** (2 < |ΔT| ≤ 5 °C) → **60 %** AC‑a, pali se LED2.
  * **Brzina 3** (|ΔT| > 5 °C)  → **100 %** AC‑a, pali se LED3.
* **Low‑regime (SW1 = OPEN)** → uvek Brzina 1 na **10 %** AC‑a.
* **Window open (SW2 = CLOSED)** → klima ugašena, sve LED‑ice pogašene.
* **SCADA** i dalje može da postavi `target_temp` upisom u measurement **`config`**.

Influx primer
--------------
```bash
# Cilj na 23 °C
influx -database mydb -execute "INSERT config target_temp=23"
```

Pin‑out: SW1=23, SW2=24, LED‑ovi na 17/27/22.
"""

from __future__ import annotations

import glob, os, time
from dataclasses import dataclass
import RPi.GPIO as GPIO
from influxdb import InfluxDBClient

# ───────── pinout & konstante ───────────────────────────────────────
PIN_SW1, PIN_SW2 = 23, 24
PIN_LED1, PIN_LED2, PIN_LED3 = 17, 27, 22
PWM_FREQ = 1000  # Hz

DEFAULT_TARGET  = 22.0  # °C
LOG_INTERVAL    = 5.0   # s

# Fiksni intenziteti za svaku brzinu (%)
SPEED_LEVEL = {1: 25.0, 2: 60.0, 3: 100.0}
LOW_INTENSITY = 10.0  # Low režim

INFLUX = {
    'host': 'localhost', 'port': 8086,
    'username': 'admin', 'password': 'mia',
    'database': 'mydb',  'measurement': 'environment',
}

# ───────── DS18B20 helperi ──────────────────────────────────────────

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

# ───────── data strukture ──────────────────────────────────────────
@dataclass
class SwitchState:
    auto_mode: bool      # SW1 zatvoren (LOW) = AUTO, OPEN = LOW režim
    window_open: bool    # SW2 zatvoren (LOW) = prozor otvoren ⇒ stop

@dataclass
class ClimateCommand:
    fan_speed: int       # 0–3
    ac_intensity: float  # 0–100 %

# ───────── logika ──────────────────────────────────────────────────

def read_switches() -> SwitchState:
    return SwitchState(GPIO.input(PIN_SW1) == GPIO.LOW,
                       GPIO.input(PIN_SW2) == GPIO.LOW)


def compute_command(temp: float, tgt: float, sw: SwitchState) -> ClimateCommand:
    # Prozor otvoren → OFF
    if sw.window_open:
        return ClimateCommand(0, 0.0)

    delta = abs(temp - tgt)

    # Low režim: brzina 1 @ 10 %
    if not sw.auto_mode:
        return ClimateCommand(1, LOW_INTENSITY)

    # AUTO: fiksne vrednosti po delta‑opsegu
    if delta <= 2:
        return ClimateCommand(1, SPEED_LEVEL[1])
    elif delta <= 5:
        return ClimateCommand(2, SPEED_LEVEL[2])
    else:
        return ClimateCommand(3, SPEED_LEVEL[3])


def update_led_bar(fan_speed: int, pwms):
    """Pali isključivo jednu LED‑ice po brzini; ničim ne upravlja kad je OFF."""
    p1, p2, p3 = pwms
    p1.ChangeDutyCycle(0); p2.ChangeDutyCycle(0); p3.ChangeDutyCycle(0)

    if fan_speed == 1:
        p1.ChangeDutyCycle(100)
    elif fan_speed == 2:
        p2.ChangeDutyCycle(100)
    elif fan_speed == 3:
        p3.ChangeDutyCycle(100)
    # fan_speed 0 ⇒ sve pogašeno

# ───────── Influx helpers ───────────────────────────────────────────

def influx_client():
    return InfluxDBClient(host=INFLUX['host'], port=INFLUX['port'],
                          username=INFLUX['username'], password=INFLUX['password'],
                          database=INFLUX['database'])


def fetch_target(cli, current: float) -> float:
    try:
        res = cli.query('SELECT LAST(target_temp) FROM config')
        if res:
            val = list(res.get_points())[0]['last']
            return float(val)
    except Exception:
        pass
    return current


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

# ───────── main petlja ──────────────────────────────────────────────

def main():
    sensor = setup_sensor()
    pwms   = setup_gpio()
    cli    = influx_client()
    target = DEFAULT_TARGET
    print('Controller – tri brzine (fiks %), Low rež, Window stop. Ctrl‑C za exit')
    try:
        while True:
            target = fetch_target(cli, target)
            temp = read_temp(sensor)
            if temp is None:
                time.sleep(LOG_INTERVAL); continue
            sw  = read_switches()
            cmd = compute_command(temp, target, sw)
            update_led_bar(cmd.fan_speed, pwms)
            log_point(cli, temp, cmd, sw, target, mode)
            mode = 'WIN' if sw.window_open else 'AUTO' if sw.auto_mode else 'LOW'
            print(f"{time.strftime('%H:%M:%S')}  T={temp:5.2f}°C  Set={target:.2f}°C  {mode:<4}  FAN={cmd.fan_speed}  AC={cmd.ac_intensity:5.1f}%")
            time.sleep(LOG_INTERVAL)
    except KeyboardInterrupt:
        print('\nBye')
    finally:
        for p in pwms:
            p.stop()
        GPIO.cleanup()

if __name__ == '__main__':
    main()
