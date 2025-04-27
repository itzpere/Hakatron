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
import glob, os, time, sys
from dataclasses import dataclass
import traceback
import RPi.GPIO as GPIO
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError

# ───────── pinout & constants ───────────────────────────────────────
PIN_SW1, PIN_SW2 = 23, 24

LOG_INTERVAL = 1.0  # s - 1 second regular updates
CONFIG_CHECK_INTERVAL = 10.0  # s - check config less frequently

# The host should be the IP address or hostname of the machine running InfluxDB
# If InfluxDB is running on the same machine, use 'localhost'
# If running on a different machine, use that machine's IP address
INFLUX = {
    'host': '10.147.18.192',  # Changed to the known lab server IP
    'port': 8086,
    'username': 'admin', 
    'password': 'mia',
    'database': 'mydb',  
    'measurement': 'pi',
    'retention_policy': 'autogen'  # Add explicit retention policy
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

def check_data_exists(cli):
    """Verify that we can read data from the database"""
    try:
        results = cli.query(f"SELECT * FROM {INFLUX['measurement']} ORDER BY time DESC LIMIT 5")
        points = list(results.get_points())
        if points:
            print(f"Found {len(points)} recent data points in database:")
            for point in points:
                print(f"  - {point['time']}: temp={point.get('sensors_temp')}, window={point.get('window_open')}, presence={point.get('presence')}")
            return True
        else:
            print(f"No data found in measurement '{INFLUX['measurement']}'")
            return False
    except Exception as e:
        print(f"Error checking data: {e}")
        return False

def log_sensor_data(cli, temp, sw):
    """Log only sensor data to the database with error handling"""
    if cli is None:
        print("No database connection, skipping data logging")
        return False
        
    try:
        from datetime import datetime
        
        # Create a timestamp - important for InfluxDB
        current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        fields = {
            'sensors_temp': float(temp),  # Ensure it's a float
            'window_open': int(sw.window_open),
            'presence': int(sw.auto_mode),  # Using auto_mode pin to represent presence
        }
        
        point = {
            'measurement': INFLUX['measurement'],
            'time': current_time,
            'fields': fields
        }
        
        print(f"Sending to InfluxDB: {point}")
        result = cli.write_points(
            [point], 
            time_precision='ms',
            retention_policy=INFLUX['retention_policy']
        )
        
        if result:
            print(f"Successfully wrote data to InfluxDB")
        else:
            print(f"Failed to write data to InfluxDB")
            
        return result
    except InfluxDBClientError as e:
        print(f"InfluxDB client error while logging: {e}")
        return False
    except InfluxDBServerError as e:
        print(f"InfluxDB server error while logging: {e}")
        return False
    except Exception as e:
        print(f"Error logging data to InfluxDB: {e}")
        traceback.print_exc()
        return False

def influx_client():
    """Set up a connection to InfluxDB with error handling"""
    try:
        client = InfluxDBClient(
            host=INFLUX['host'], 
            port=INFLUX['port'],
            username=INFLUX['username'], 
            password=INFLUX['password'],
            database=None,  # Don't set database yet
            timeout=5       # Add timeout
        )
        
        # Check connection by getting server version
        version = client.ping()
        print(f"Connected to InfluxDB server: {version}")
        
        # Check if database exists, create if it doesn't
        dbs = [db['name'] for db in client.get_list_database()]
        print(f"Available databases: {dbs}")
        
        if INFLUX['database'] not in dbs:
            print(f"Creating database '{INFLUX['database']}'...")
            client.create_database(INFLUX['database'])
        
        # Switch to the specified database
        client.switch_database(INFLUX['database'])
        print(f"Using database: {INFLUX['database']}")
        
        # Check if we have any data
        check_data_exists(client)
        
        return client
        
    except InfluxDBClientError as e:
        print(f"InfluxDB client error: {e}")
        return None
    except InfluxDBServerError as e:
        print(f"InfluxDB server error: {e}")
        return None
    except Exception as e:
        print(f"Error connecting to InfluxDB: {e}")
        traceback.print_exc()
        return None

# ───────── main loop ───────────────────────────────────────────────

def main():
    try:
        sensor = setup_sensor()
        setup_gpio()
    except Exception as e:
        print(f"Error setting up sensors: {e}")
        sys.exit(1)
    
    # Connect to InfluxDB
    cli = influx_client()
    if cli is None:
        print("Warning: Failed to connect to InfluxDB. Will retry periodically.")
    
    # Track previous sensor states to detect changes
    prev_window_state = False
    prev_auto_mode = True
    
    last_loop = time.time()
    last_db_retry = time.time()
    db_retry_interval = 30  # seconds
    last_data_check = time.time()
    data_check_interval = 60  # Check for data in the database every 60 seconds

    print('Sensor Controller running… Ctrl-C to exit')
    try:
        while True:
            now = time.time()
            last_loop = now
            
            # Try to reconnect to database if connection was lost
            if cli is None and (now - last_db_retry) >= db_retry_interval:
                print("Attempting to reconnect to InfluxDB...")
                cli = influx_client()
                last_db_retry = now
            
            # Periodically check if data exists in database
            if cli and (now - last_data_check) >= data_check_interval:
                print("\nVerifying data in the database:")
                check_data_exists(cli)
                last_data_check = now
                print() # Add a blank line for readability

            # Read temperature sensor
            try:
                temp = read_temp(sensor)
                if temp is None:
                    print("Temperature sensor read error")
                    time.sleep(min(1.0, LOG_INTERVAL))
                    continue
            except Exception as e:
                print(f"Error reading temperature: {e}")
                temp = 22.0  # Default fallback value
            
            # Read switch sensors
            try:
                sw = read_switches()
            except Exception as e:
                print(f"Error reading switches: {e}")
                sw = SwitchState(auto_mode=prev_auto_mode, window_open=prev_window_state)
            
            # Check for sensor changes that should be logged immediately
            sensor_changed = (sw.window_open != prev_window_state or 
                             sw.auto_mode != prev_auto_mode)
            
            # Immediately log any sensor changes to the database
            if sensor_changed:
                print(f"Sensor change detected: window={sw.window_open}, presence={sw.auto_mode}")
                log_sensor_data(cli, temp, sw)
            
            # Store current states for next comparison
            prev_window_state = sw.window_open
            prev_auto_mode = sw.auto_mode
            
            # Regular logging at each interval
            log_result = log_sensor_data(cli, temp, sw)
            db_status = "OK" if log_result else "FAIL"

            print(f"{time.strftime('%H:%M:%S')}  "
                  f"T={temp:5.2f}°C  "
                  f"Window={'OPEN' if sw.window_open else 'CLOSED'}  "
                  f"Presence={'DETECTED' if sw.auto_mode else 'NONE'}  "
                  f"DB={db_status}")

            time.sleep(LOG_INTERVAL)

    except KeyboardInterrupt:
        print('\nBye')
    except Exception as e:
        print(f"Unexpected error: {e}")
        traceback.print_exc()
    finally:
        try:
            GPIO.cleanup()
        except:
            pass

if __name__ == '__main__':
    main()
