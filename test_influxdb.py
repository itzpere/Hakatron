from influxdb import InfluxDBClient
from datetime import datetime
import time
import sys
import os

# Add some industrial-style terminal formatting
class TermColors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# InfluxDB connection parameters - update as needed
INFLUXDB_URL = "localhost"  # Try with localhost instead of IP
INFLUXDB_PORT = 8086
INFLUXDB_USER = "admin"
INFLUXDB_PASSWORD = "mia"
INFLUXDB_DATABASE = "mydb"

def test_influxdb_connection():
    """Test basic connection to InfluxDB server"""
    print(f"\n{TermColors.HEADER}===== TESTING INFLUXDB CONNECTION ====={TermColors.ENDC}\n")
    
    try:
        print(f"{TermColors.CYAN}[INFO]{TermColors.ENDC} Connecting to InfluxDB at {INFLUXDB_URL}:{INFLUXDB_PORT}...")
        client = InfluxDBClient(
            host=INFLUXDB_URL,
            port=INFLUXDB_PORT,
            username=INFLUXDB_USER,
            password=INFLUXDB_PASSWORD
        )
        client.ping()
        print(f"{TermColors.GREEN}[SUCCESS]{TermColors.ENDC} Connected to InfluxDB")
        return client
    except Exception as e:
        print(f"{TermColors.FAIL}[ERROR]{TermColors.ENDC} Connection failed: {e}")
        return None

def test_database_operations(client):
    """Test database operations like listing and creating databases"""
    print(f"\n{TermColors.HEADER}===== TESTING DATABASE OPERATIONS ====={TermColors.ENDC}\n")
    
    if client is None:
        print(f"{TermColors.WARNING}[WARNING]{TermColors.ENDC} No client connection available. Skipping database tests.")
        return False
    
    try:
        # List databases
        print(f"{TermColors.CYAN}[INFO]{TermColors.ENDC} Listing available databases...")
        dbs = client.get_list_database()
        print(f"{TermColors.GREEN}[SUCCESS]{TermColors.ENDC} Found {len(dbs)} databases:")
        for db in dbs:
            print(f"  - {db['name']}")
        
        # Check if our database exists or create it
        db_exists = False
        for db in dbs:
            if db['name'] == INFLUXDB_DATABASE:
                db_exists = True
                break
        
        if not db_exists:
            print(f"{TermColors.CYAN}[INFO]{TermColors.ENDC} Creating database '{INFLUXDB_DATABASE}'...")
            client.create_database(INFLUXDB_DATABASE)
            print(f"{TermColors.GREEN}[SUCCESS]{TermColors.ENDC} Database created")
        else:
            print(f"{TermColors.CYAN}[INFO]{TermColors.ENDC} Database '{INFLUXDB_DATABASE}' already exists")
        
        # Switch to our database
        client.switch_database(INFLUXDB_DATABASE)
        print(f"{TermColors.GREEN}[SUCCESS]{TermColors.ENDC} Switched to database '{INFLUXDB_DATABASE}'")
        
        return True
    except Exception as e:
        print(f"{TermColors.FAIL}[ERROR]{TermColors.ENDC} Database operation failed: {e}")
        return False

def test_write_data(client):
    """Test writing data points to InfluxDB"""
    print(f"\n{TermColors.HEADER}===== TESTING WRITING DATA ====={TermColors.ENDC}\n")
    
    if client is None:
        print(f"{TermColors.WARNING}[WARNING]{TermColors.ENDC} No client connection available. Skipping write tests.")
        return False
    
    try:
        # Current time and test values
        current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        test_temp = 23.5
        test_humid = 45.0
        
        # Prepare JSON data for InfluxDB
        json_body = [
            {
                "measurement": "temperature",
                "tags": {
                    "host": "test_host",
                    "location": "office"
                },
                "time": current_time,
                "fields": {
                    "value": test_temp
                }
            },
            {
                "measurement": "humidity",
                "tags": {
                    "host": "test_host",
                    "location": "office"
                },
                "time": current_time,
                "fields": {
                    "value": test_humid
                }
            }
        ]
        
        print(f"{TermColors.CYAN}[INFO]{TermColors.ENDC} Writing test data points...")
        client.write_points(json_body)
        print(f"{TermColors.GREEN}[SUCCESS]{TermColors.ENDC} Data written successfully")
        
        # Return values for testing read
        return True
    except Exception as e:
        print(f"{TermColors.FAIL}[ERROR]{TermColors.ENDC} Writing data failed: {e}")
        return False

def test_read_data(client):
    """Test reading back the data we just wrote"""
    print(f"\n{TermColors.HEADER}===== TESTING READING DATA ====={TermColors.ENDC}\n")
    
    if client is None:
        print(f"{TermColors.WARNING}[WARNING]{TermColors.ENDC} No client connection available. Skipping read tests.")
        return False
    
    # Give a short delay to ensure data is fully written
    time.sleep(1)
    
    try:
        print(f"{TermColors.CYAN}[INFO]{TermColors.ENDC} Reading temperature data...")
        temp_query = 'SELECT * FROM "temperature" ORDER BY time DESC LIMIT 10'
        temp_result = client.query(temp_query)
        temp_points = list(temp_result.get_points())
        
        print(f"{TermColors.CYAN}[INFO]{TermColors.ENDC} Reading humidity data...")
        humid_query = 'SELECT * FROM "humidity" ORDER BY time DESC LIMIT 10'
        humid_result = client.query(humid_query)
        humid_points = list(humid_result.get_points())
        
        # Check if we got any data back
        if temp_points:
            print(f"{TermColors.GREEN}[SUCCESS]{TermColors.ENDC} Retrieved {len(temp_points)} temperature points:")
            for point in temp_points[:3]:  # Show up to 3 points
                print(f"  - Time: {point['time']}, Value: {point['value']}")
                
        else:
            print(f"{TermColors.WARNING}[WARNING]{TermColors.ENDC} No temperature data found")
            
        if humid_points:
            print(f"{TermColors.GREEN}[SUCCESS]{TermColors.ENDC} Retrieved {len(humid_points)} humidity points:")
            for point in humid_points[:3]:  # Show up to 3 points
                print(f"  - Time: {point['time']}, Value: {point['value']}")
        else:
            print(f"{TermColors.WARNING}[WARNING]{TermColors.ENDC} No humidity data found")
            
        return len(temp_points) > 0 or len(humid_points) > 0
    except Exception as e:
        print(f"{TermColors.FAIL}[ERROR]{TermColors.ENDC} Reading data failed: {e}")
        return False

def run_all_tests():
    """Run all tests in sequence"""
    print(f"\n{TermColors.BOLD}{TermColors.HEADER}🔍 Starting InfluxDB Connection Tests 🔍{TermColors.ENDC}\n")
    
    # Step 1: Test connection
    client = test_influxdb_connection()
    if client is None:
        print(f"\n{TermColors.FAIL}[CRITICAL]{TermColors.ENDC} Could not establish connection to InfluxDB. Check connection parameters and server status.")
    
    # Step 1: Test connection
    client = test_influxdb_connection()
    if client is None:
        print("\n❌ CONNECTION FAILED: Could not establish connection to InfluxDB")
        print("Suggestions:")
        print("  1. Make sure InfluxDB is installed and running")
        print("  2. Check if the service is running with: systemctl status influxdb")
        print("  3. Try connecting with 'localhost' instead of IP address")
        print("  4. Verify your username and password are correct")
        return False
    
    # Step 2: Test database operations
    db_success = test_database_operations(client)
    if not db_success:
        print("\n❌ DATABASE OPERATIONS FAILED: Could not manage the database")
        print("Suggestions:")
        print("  1. Check if your user has permission to create databases")
        print("  2. Try manually creating the database: influx -username admin -password mia -execute 'CREATE DATABASE mydb'")
        return False
    
    # Step 3: Test writing data
    write_success = test_write_data(client)
    if not write_success:
        print("\n❌ WRITE OPERATIONS FAILED: Could not write data to InfluxDB")
        print("Suggestions:")
        print("  1. Check if your user has write permissions")
        print("  2. Verify the database exists and is selected")
        return False
    
    # Step 4: Test reading data
    read_success = test_read_data(client)
    if not read_success:
        print("\n❌ READ OPERATIONS FAILED: Could not read data from InfluxDB")
        print("Suggestions:")
        print("  1. Check if your user has read permissions")
        print("  2. Verify the database contains data")
        return False
    
    # All tests passed!
    print("\n✅ ALL TESTS PASSED! InfluxDB is working correctly.")
    print("\nFor your dashboard.py file:")
    print(f"  1. Make sure INFLUXDB_URL is set to '{INFLUXDB_URL}'")
    print("  2. Make sure the credentials match those used in this test")
    print("  3. Make sure the query syntax in your callbacks matches InfluxDB v1.x")
    
    return True

if __name__ == "__main__":
    run_all_tests()