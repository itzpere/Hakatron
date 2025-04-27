#!/usr/bin/env python3
"""
Raspberry Pi Sensor Controller
=======================================

This script reads sensor data and sends it to the database.
It focuses solely on data acquisition, not control logic.

Sensors:
- Temperature (DS18B20)
- Window state (switch)
- Mode state (switch)
"""
from __future__ import annotations
import glob, os, time
from dataclasses import dataclass
import RPi.GPIO as GPIO
from influxdb import InfluxDBClient

# ───────── pinout & constants ───────────────────────────────────────
PIN_SW1, PIN_SW2 = 23, 24

LOG_INTERVAL = 2.5  # s - 1 second regular updates
CONFIG_CHECK_INTERVAL = 10.0  # s - check config less frequently

INFLUX = {
    'host': 'localhost', 'port': 8086,
    'username': 'admin', 'password': 'mia',
    'database': 'mydb',  'measurement': 'pi',
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

# ───────── GPIO setup ─────────────────────────────────────────────

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup([PIN_SW1, PIN_SW2], GPIO.IN, pull_up_down=GPIO.PUD_UP)
    return None

# ───────── data structures ──────────────────────────────────────────
@dataclass
class SwitchState:
    auto_mode: bool      # True = AUTO, False = LOW
    window_open: bool

# ───────── sensor reading ─────────────────────────────────────────

def read_switches() -> SwitchState:
    return SwitchState(GPIO.input(PIN_SW1) == GPIO.LOW,
                      GPIO.input(PIN_SW2) == GPIO.LOW)

# ───────── Influx helpers ──────────────────────────────────────────

def influx_client():
    return InfluxDBClient(**{k: INFLUX[k]
                             for k in ('host', 'port', 'username', 'password', 'database')})

def log_sensor_data(cli, temp, sw):
    """Log only sensor data to the database with error handling"""
    # Round temperature to 3 decimal places for consistency
    temp = round(temp, 3)
    
    # Create timestamp in nanoseconds using current time
    current_time = int(time.time() * 1000000000)
    
    fields = {
        'sensors_temp': temp,
        'window_open': int(sw.window_open),
        'presence': int(sw.auto_mode),  # Using auto_mode pin to represent presence
    }
    
    point = {
        'measurement': INFLUX['measurement'], 
        'fields': fields,
        'time': current_time  # Explicitly set the timestamp
    }
    
    try:
        result = cli.write_points([point], time_precision='n')
        if not result:
            print(f"WARNING: Database write failed at {time.strftime('%H:%M:%S')}")
            return False
        return True
    except Exception as e:
        print(f"ERROR: Database write exception: {e}")
        return False

def check_connection(cli):
    """Check if database connection is healthy"""
    try:
        # Simple ping to verify connection
        cli.ping()
        return True
    except Exception:
        return False

# ───────── main loop ───────────────────────────────────────────────

def main():
    sensor = setup_sensor()
    setup_gpio()
    cli = influx_client()
    
    # Track previous sensor states to detect changes
    prev_window_state = False
    prev_auto_mode = True
    
    last_loop = time.time()

    print('Sensor Controller running… Ctrl-C to exit')
    try:
        while True:
            now = time.time()
            last_loop = now

            # Read temperature sensor
            temp = read_temp(sensor)
            if temp is None:
                print("Temperature sensor read error")
                time.sleep(min(1.0, LOG_INTERVAL))
                continue

            # Read switch sensors
            sw = read_switches()
            
            # Check for sensor changes that should be logged immediately
            sensor_changed = (sw.window_open != prev_window_state or 
                             sw.auto_mode != prev_auto_mode)

            # Only write once per loop iteration
            write_success = False
            retry_count = 0
            max_retries = 3

            while not write_success and retry_count < max_retries:
                if retry_count > 0:
                    print(f"Retry attempt {retry_count}/{max_retries}")
                
                # Check connection before attempting write
                if not check_connection(cli):
                    print("Database connection lost, reconnecting...")
                    try:
                        cli = influx_client()
                    except Exception as e:
                        print(f"Reconnection failed: {e}")
                        time.sleep(1)  # Wait before retry
                        retry_count += 1
                        continue
                        
                # Now attempt the write
                if sensor_changed:
                    print(f"Sensor change detected: window={sw.window_open}, presence={sw.auto_mode}")
                write_success = log_sensor_data(cli, temp, sw)
                retry_count += 1

            if not write_success:
                # Try to reconnect if write failed
                print("Attempting to reconnect to database...")
                try:
                    cli = influx_client()
                except Exception as e:
                    print(f"Reconnection failed: {e}")

            # Store current states for next comparison
            prev_window_state = sw.window_open
            prev_auto_mode = sw.auto_mode

            print(f"{time.strftime('%H:%M:%S')}  "
                  f"T={temp:5.2f}°C  "
                  f"Window={'OPEN' if sw.window_open else 'CLOSED'}  "
                  f"Presence={'DETECTED' if sw.auto_mode else 'NONE'}")

            time.sleep(LOG_INTERVAL)

    except KeyboardInterrupt:
        print('\nBye')
    finally:
        GPIO.cleanup()

if __name__ == '__main__':
    main()
