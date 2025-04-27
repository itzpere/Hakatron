from influxdb import InfluxDBClient
import datetime
import time

# InfluxDB Connection Parameters (same as in app.py)
INFLUXDB_URL = "10.147.18.192"
INFLUXDB_PORT = 8086
INFLUXDB_USER = "admin"
INFLUXDB_PASSWORD = "mia"
INFLUXDB_DATABASE = "mydb"

# Initialize InfluxDB client
try:
    client = InfluxDBClient(
        host=INFLUXDB_URL,
        port=INFLUXDB_PORT,
        username=INFLUXDB_USER,
        password=INFLUXDB_PASSWORD
    )
    client.switch_database(INFLUXDB_DATABASE)
    print("Alert logic connected to InfluxDB")
except Exception as e:
    print(f"Error initializing InfluxDB client in alerts logic: {e}")
    client = None

def add_alert(device, message, severity="medium"):
    """
    Add a new alert to InfluxDB
    """
    if client is None:
        print("Cannot add alert: No database connection")
        return False
    
    try:
        # Create a unique ID
        alert_id = int(datetime.datetime.now().timestamp())
        
        # Prepare the data point
        json_body = [
            {
                "measurement": "alerts",
                "tags": {
                    "device": device,
                    "severity": severity
                },
                "fields": {
                    "alert_id": alert_id,
                    "message": message,
                    "device": device,
                    "severity": severity
                }
            }
        ]
        
        # Write to InfluxDB
        success = client.write_points(json_body)
        return success
    except Exception as e:
        print(f"Error adding alert: {e}")
        return False

def check_window_sensor(sensor_id, is_open, location=None):
    """
    Generate alerts based on window sensor state
    
    Parameters:
    - sensor_id: Identifier for the window sensor
    - is_open: Boolean indicating if window is open (True) or closed (False)
    - location: Optional location description (e.g., "Kitchen", "Bedroom")
    
    Returns:
    - Boolean indicating if alert was successfully added
    """
    device_name = f"Window Sensor {sensor_id}"
    if location:
        device_name += f" ({location})"
        
    if is_open:
        # Generate alert for open window
        message = f"Window {sensor_id} is open"
        if location:
            message = f"{location} window is open"
            
        # Determine severity (can be adjusted based on business rules)
        current_hour = datetime.datetime.now().hour
        
        # Higher severity during nighttime (10PM-6AM) or if explicitly marked as security concern
        if 22 <= current_hour or current_hour < 6:
            severity = "high"
            message += " during nighttime hours"
        else:
            severity = "medium"
            
        # Add the alert to the database
        return add_alert(device_name, message, severity)
    else:
        # Optionally log window closing (as low severity or just for monitoring)
        # Uncomment if you want alerts when windows close too
        # message = f"Window {sensor_id} has been closed"
        # if location:
        #     message = f"{location} window has been closed"
        # return add_alert(device_name, message, "low")
        return True  # No alert needed for closed windows

# Example usage:
# check_window_sensor("W101", True, "Living Room")  # Window is open
# check_window_sensor("W102", False, "Bedroom")     # Window is closed