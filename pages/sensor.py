import dash
from dash import dcc, html, callback
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
from datetime import datetime
import random

# Define all configuration variables at the top
DEVICE_NAME = "pi"
USE_RANDOM_DATA = False  # Changed from True to False to prioritize database values
RANDOM_TEMP_MIN = 18
RANDOM_TEMP_MAX = 30
RANDOM_VARIATION = 0.5
MAX_DATA_POINTS = 100

# Device state - new variable to track if device is on or off
DEVICE_ON = True  # Default to on

# Temperature mode settings
PID_TEMP = 22
AUTOMATIC_TEMP = 20
ACTIVE_MODE = "Automatic"  # Default mode changed from "Ručni" to "Automatic"

# Control state variables (enabled/disabled)
temp_control_disabled = True  # Set to True for Automatic mode
fan_control_disabled = True   # Set to True for Automatic mode

# Heater control settings
DEFAULT_TARGET_TEMP = 22
TEMP_HYSTERESIS = 0.5  # Prevents heater from cycling too frequently
heater_state = False  # Off by default
target_temperature = DEFAULT_TARGET_TEMP
heater_history = {'time': [], 'state': []}

# Fan control settings
fan_speed = 0  # Initial fan speed (0-100)
fan_history = {'time': [], 'speed': []}  # Add history tracking for fan

# Sensor states and history
movement_detected = False  # Off by default
window_open = False  # Closed by default
movement_history = {'time': [], 'state': []}
window_history = {'time': [], 'state': []}

# Sensor settings
MOVEMENT_PROBABILITY = 0.1  # 10% chance of movement change
WINDOW_PROBABILITY = 0.05   # 5% chance of window state change
SENSOR_ON_COLOR = '#4CAF50'  # Green
SENSOR_OFF_COLOR = 'gray'

# InfluxDB connection parameters
INFLUXDB_URL = "10.147.18.192"  # You may need to change this to the actual host if not localhost
INFLUXDB_PORT = 8086
INFLUXDB_USER = "admin"
INFLUXDB_PASSWORD = "mia"
INFLUXDB_DATABASE = "mydb"
MAX_RETRY_ATTEMPTS = 3  # Number of times to retry connection
CONNECTION_TIMEOUT = 5  # Timeout in seconds

# Temperature ranges for display (will be overridden by dynamic values)
TEMP_RANGE_COLD = 20
TEMP_RANGE_COMFORTABLE = 24
TEMP_RANGE_WARM = 28

# Default min/max values that will be updated dynamically
temp_display_min = 15
temp_display_max = 35

# Temperature display settings
COLD_COLOR = 'blue'
COMFORTABLE_COLOR = 'green'
WARM_COLOR = 'orange'
HOT_COLOR = 'red'
HEATER_ON_COLOR = 'red'
HEATER_OFF_COLOR = 'gray'

# Initialize temperature data storage
temp_data = {'time': [], 'temperature': []}

# Function to calculate dynamic min/max based on data
def calculate_dynamic_ranges():
    global temp_display_min, temp_display_max, TEMP_RANGE_COLD, TEMP_RANGE_COMFORTABLE, TEMP_RANGE_WARM
    
    # If we have temperature data
    if temp_data['temperature']:
        min_temp = min(temp_data['temperature'])
        max_temp = max(temp_data['temperature'])
        
        # Give some padding to the min/max
        temp_display_min = max(0, round(min_temp - 5))
        temp_display_max = round(max_temp + 5)
        
        # Calculate dynamic ranges for color thresholds
        range_size = temp_display_max - temp_display_min
        TEMP_RANGE_COLD = temp_display_min + (range_size * 0.25)
        TEMP_RANGE_COMFORTABLE = temp_display_min + (range_size * 0.5)
        TEMP_RANGE_WARM = temp_display_min + (range_size * 0.75)
    else:
        # Default values if no data
        temp_display_min = 15
        temp_display_max = 35
        TEMP_RANGE_COLD = 20
        TEMP_RANGE_COMFORTABLE = 24
        TEMP_RANGE_WARM = 28

# Function to determine heater state based on current temperature
def update_heater_state(current_temp):
    global heater_state, heater_history
    
    # Apply hysteresis to prevent rapid cycling
    if heater_state:  # If heater is on
        # Turn off only if temperature exceeds target + hysteresis
        if current_temp >= target_temperature + TEMP_HYSTERESIS:
            heater_state = False
    else:  # If heater is off
        # Turn on only if temperature drops below target - hysteresis
        if current_temp < target_temperature - TEMP_HYSTERESIS:
            heater_state = True
    
    # Record heater state history
    current_time = datetime.now().strftime('%H:%M:%S')
    heater_history['time'].append(current_time)
    heater_history['state'].append(1 if heater_state else 0)
    
    # Keep only recent history
    if len(heater_history['time']) > MAX_DATA_POINTS:
        heater_history['time'] = heater_history['time'][-MAX_DATA_POINTS:]
        heater_history['state'] = heater_history['state'][-MAX_DATA_POINTS:]
    
    return heater_state

# Function to update movement sensor state (random for demo)
def update_movement_sensor():
    global movement_detected, movement_history
    
    # Randomly change movement state with low probability
    if random.random() < MOVEMENT_PROBABILITY:
        movement_detected = not movement_detected
    
    # Record state history
    current_time = datetime.now().strftime('%H:%M:%S')
    movement_history['time'].append(current_time)
    movement_history['state'].append(1 if movement_detected else 0)
    
    # Keep only recent history
    if len(movement_history['time']) > MAX_DATA_POINTS:
        movement_history['time'] = movement_history['time'][-MAX_DATA_POINTS:]
        movement_history['state'] = movement_history['state'][-MAX_DATA_POINTS:]
    
    return movement_detected

# Function to update window sensor state (random for demo)
def update_window_sensor():
    global window_open, window_history
    
    # Randomly change window state with low probability
    if random.random() < WINDOW_PROBABILITY:
        window_open = not window_open
    
    # Record state history
    current_time = datetime.now().strftime('%H:%M:%S')
    window_history['time'].append(current_time)
    window_history['state'].append(1 if window_open else 0)
    
    # Keep only recent history
    if len(window_history['time']) > MAX_DATA_POINTS:
        window_history['time'] = window_history['time'][-MAX_DATA_POINTS:]
        window_history['state'] = window_history['state'][-MAX_DATA_POINTS:]
    
    return window_open

# Register the page
dash.register_page(__name__, path=f'/{DEVICE_NAME}', title='Temperature Dashboard', name='Temperature')

# Import InfluxDB
try:
    from influxdb import InfluxDBClient
    influxdb_available = True
except ImportError:
    influxdb_available = False

# Function to check if data is recent enough to be considered valid
def is_data_recent(timestamp_str, max_age_seconds=30):
    """Check if a timestamp is recent enough to be considered valid"""
    if not timestamp_str:
        return False
    try:
        # Parse the timestamp
        from dateutil import parser
        import pytz
        from datetime import datetime, timedelta
        
        # Parse the timestamp string
        dt = parser.parse(timestamp_str)
        
        # Make sure it's timezone aware
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        
        # Get current time
        now = datetime.now(pytz.UTC)
        
        # Check if data is recent
        return (now - dt) <= timedelta(seconds=max_age_seconds)
    except Exception as e:
        print(f"Error checking data freshness: {e}")
        return False

# Function to fetch latest sensor values from database
def fetch_latest_sensor_data():
    global temp_data, fan_speed, window_open, movement_detected, target_temperature, ACTIVE_MODE, temp_control_disabled, fan_control_disabled
    
    if client is None:
        print("No database connection, using random data")
        return False

    try:
        # Get the latest temperature - changed table name from environment to pi
        temp_result = client.query('SELECT LAST(sensors_temp) FROM pi')
        if temp_result:
            points = list(temp_result.get_points())
            if points:
                latest_temp = points[0]['last']
                latest_time = points[0]['time']
                
                if is_data_recent(latest_time):
                    # Only update if we have temperature data
                    if latest_temp is not None:
                        # Add to our data store
                        temp_data['time'].append(datetime.now().strftime('%H:%M:%S'))
                        temp_data['temperature'].append(latest_temp)
                        
                        # Keep only most recent data points
                        if len(temp_data['time']) > MAX_DATA_POINTS:
                            temp_data['time'] = temp_data['time'][-MAX_DATA_POINTS:]
                            temp_data['temperature'] = temp_data['temperature'][-MAX_DATA_POINTS:]
        
        # Note: ac_intensity is no longer available in the pi table
        # Using default or currently stored fan speed
        
        # Get the latest window state - changed table from environment to pi
        window_result = client.query('SELECT LAST(window_open) FROM pi')
        if window_result:
            points = list(window_result.get_points())
            if points and points[0]['last'] is not None:
                window_open = bool(int(points[0]['last']))
                
                # Update window history
                current_time = datetime.now().strftime('%H:%M:%S')
                window_history['time'].append(current_time)
                window_history['state'].append(1 if window_open else 0)
                
                # Keep only recent history
                if len(window_history['time']) > MAX_DATA_POINTS:
                    window_history['time'] = window_history['time'][-MAX_DATA_POINTS:]
                    window_history['state'] = window_history['state'][-MAX_DATA_POINTS:]
        
        # Get the latest movement state (presence field) - changed from environment to pi
        movement_result = client.query('SELECT LAST(presence) FROM pi')
        if movement_result:
            points = list(movement_result.get_points())
            if points and points[0]['last'] is not None:
                movement_detected = bool(int(points[0]['last']))
                
                # Update movement history
                current_time = datetime.now().strftime('%H:%M:%S')
                movement_history['time'].append(current_time)
                movement_history['state'].append(1 if movement_detected else 0)
                
                # Keep only recent history
                if len(movement_history['time']) > MAX_DATA_POINTS:
                    movement_history['time'] = movement_history['time'][-MAX_DATA_POINTS:]
                    movement_history['state'] = movement_history['state'][-MAX_DATA_POINTS:]
        
        # Note: target_temp and mode are no longer available in the pi table
        # Using default values or current values
        
        return True
    except Exception as e:
        print(f"Error fetching sensor data from database: {e}")
        return False

# Initialize InfluxDB client if available
client = None
connection_error = None
if influxdb_available:
    try:
        # Import with timeout support
        import urllib3
        import time  # Add explicit import here to ensure it's available
        from requests.exceptions import ConnectionError
        
        # Set a timeout for the connection
        urllib3.util.Timeout(connect=CONNECTION_TIMEOUT, read=CONNECTION_TIMEOUT)
        
        # Try to connect with retries
        retry_count = 0
        while retry_count < MAX_RETRY_ATTEMPTS:
            try:
                client = InfluxDBClient(
                    host=INFLUXDB_URL,
                    port=INFLUXDB_PORT,
                    username=INFLUXDB_USER,
                    password=INFLUXDB_PASSWORD,
                    database=INFLUXDB_DATABASE,
                    timeout=CONNECTION_TIMEOUT
                )
                print(f"Successfully connected to InfluxDB on attempt {retry_count+1}")
                
                # Test the connection by querying the database list
                databases = client.get_list_database()
                print(f"Available databases: {databases}")
                
                # Check if our database exists
                if any(db['name'] == INFLUXDB_DATABASE for db in databases):
                    print(f"Database '{INFLUXDB_DATABASE}' found!")
                else:
                    print(f"Database '{INFLUXDB_DATABASE}' not found!")
                    # Create the database if it doesn't exist
                    client.create_database(INFLUXDB_DATABASE)
                    print(f"Created database '{INFLUXDB_DATABASE}'")
                
                # Switch to our database
                client.switch_database(INFLUXDB_DATABASE)
                
                # Connection successful, break the retry loop
                break
            
            except ConnectionError as e:
                retry_count += 1
                connection_error = str(e)
                print(f"Connection attempt {retry_count} failed: {e}")
                if retry_count < MAX_RETRY_ATTEMPTS:
                    print(f"Retrying in 2 seconds...")
                    time.sleep(2)  # Now time should be defined
                else:
                    print(f"Max retry attempts reached. Falling back to random data.")
                    USE_RANDOM_DATA = True
                    client = None
            
        # If we still don't have a client after all retries
        if client is None:
            print("Could not connect to InfluxDB. Using random data instead.")
            USE_RANDOM_DATA = True
        else:
            # Try to fetch initial values
            if not fetch_latest_sensor_data():
                print("Could not fetch latest data, falling back to random data")
                USE_RANDOM_DATA = True
    
    except Exception as e:
        connection_error = str(e)
        print(f"Database setup error: {e}")
        client = None
        USE_RANDOM_DATA = True
else:
    USE_RANDOM_DATA = True
    connection_error = "InfluxDB client not available (module not installed)"
    print("Using random data for temperature values (InfluxDB not available)")

# Define a unique ID for the fan speed output to avoid conflicts
FAN_SPEED_OUTPUT_ID = 'fan-speed-output-v1'

# Define the layout for just this page (without the navbar which is in app.py)
layout = html.Div([
    # Store component to track device state (on/off)
    dcc.Store(id='device-state', data={'on': DEVICE_ON}),
    
    # Add connection status message if there was an error
    html.Div([
        html.Div(
            f"WARNING: Using simulated data - InfluxDB connection failed: {connection_error}",
            style={
                'backgroundColor': '#fff3cd',
                'color': '#856404',
                'padding': '10px',
                'borderRadius': '5px',
                'marginBottom': '10px',
                'fontWeight': 'bold',
                'display': 'block' if USE_RANDOM_DATA and connection_error else 'none'
            }
        )
    ], style={'margin': '20px', 'marginBottom': '0px'}),
    
    # ON/OFF button at the top
    html.Div([
        html.Button(
            "TURN OFF", 
            id="device-power-button", 
            style={
                'float': 'right',
                'marginTop': '10px',
                'padding': '10px 20px',
                'backgroundColor': '#4CAF50', # Green when ON
                'color': 'white',
                'border': 'none',
                'borderRadius': '4px',
                'cursor': 'pointer',
                'fontSize': '16px',
                'fontWeight': 'bold'
            }
        ),
        html.Div([
            html.H1("Temperature Monitor", style={'display': 'inline-block'}),
            html.Div(id="device-status-indicator", 
                     style={'height': '20px', 'width': '20px', 'borderRadius': '50%', 
                            'backgroundColor': '#4CAF50', 'display': 'inline-block', 
                            'marginLeft': '15px', 'verticalAlign': 'middle'})
        ], style={'display': 'flex', 'alignItems': 'center'})
    ], style={'margin': '20px', 'marginBottom': '0px', 'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'}),
    
    # Container for all UI elements that can be hidden
    html.Div([
        # Temperature Info Panel
        html.Div([
            html.H2("Temperature Status"),
            html.Div([
                # Temperature display with mode buttons on the right
                html.Div([
                    # Left side: Temperature gauge and Fan Speed gauge side by side
                    html.Div([
                        # Organize gauges in a row
                        html.Div([
                            # Temperature gauge on the left
                            html.Div([
                                html.P("Current Temperature:", style={'fontSize': '16px', 'fontWeight': 'bold'}),
                                dcc.Graph(
                                    id='temp-gauge',
                                    figure=go.Figure(),
                                    config={'displayModeBar': False},
                                    style={'height': '200px', 'width': '100%'}
                                )
                            ], style={'width': '50%', 'display': 'inline-block', 'verticalAlign': 'top', 'paddingRight': '10px'}),
                            
                            # Fan speed gauge on the right
                            html.Div([
                                html.P("Fan Speed:", style={'fontSize': '16px', 'fontWeight': 'bold'}),
                                dcc.Graph(
                                    id='fan-gauge',
                                    figure=go.Figure(),
                                    config={'displayModeBar': False},
                                    style={'height': '200px', 'width': '100%'}
                                )
                            ], style={'width': '50%', 'display': 'inline-block', 'verticalAlign': 'top', 'paddingLeft': '10px'})
                        ], style={'display': 'flex', 'justifyContent': 'space-between'})
                    ], style={'margin': '10px', 'padding': '15px', 'backgroundColor': '#f0f0f0', 'borderRadius': '10px', 'textAlign': 'center', 'width': '70%', 'display': 'inline-block', 'verticalAlign': 'top'}),
                    
                    # Right side: Mode buttons (unchanged)
                    html.Div([
                        html.P("Temperature Mode:", style={'fontWeight': 'bold', 'marginBottom': '16px'}),
                        html.Div([
                            html.Button("PID", id="pid-mode-button", 
                                        style={'marginBottom': '10px', 'width': '100%', 'padding': '10px',
                                              'backgroundColor': '#4CAF50', 'color': 'white', 'border': 'none',
                                              'borderRadius': '4px', 'cursor': 'pointer'}),
                            
                            html.Button("Ručni", id="Ručni-mode-button", 
                                        style={'marginBottom': '10px', 'width': '100%', 'padding': '10px',
                                              'backgroundColor': '#FF9800', 'color': 'white', 'border': 'none',
                                              'borderRadius': '4px', 'cursor': 'pointer'}),
                            
                            html.Button("Automatic", id="automatic-mode-button", 
                                        style={'marginBottom': '10px', 'width': '100%', 'padding': '10px',
                                              'backgroundColor': '#2196F3', 'color': 'white', 'border': 'none',
                                              'borderRadius': '4px', 'cursor': 'pointer'}),
                                              
                            html.Button("Low", id="low-mode-button", 
                                        style={'marginBottom': '10px', 'width': '100%', 'padding': '10px',
                                              'backgroundColor': '#81D4FA', 'color': 'white', 'border': 'none',
                                              'borderRadius': '4px', 'cursor': 'pointer'}),
                                              
                            html.Button("OFF", id="off-mode-button", 
                                        style={'width': '100%', 'padding': '10px',
                                              'backgroundColor': '#f44336', 'color': 'white', 'border': 'none',
                                              'borderRadius': '4px', 'cursor': 'pointer'})
                        ]),
                        
                        html.Div([
                            html.P("Active Mode:", style={'marginTop': '15px', 'display': 'inline-block'}),
                            html.P(id="active-mode", children=ACTIVE_MODE, 
                                  style={'marginTop': '15px', 'marginLeft': '5px', 'display': 'inline-block', 'fontWeight': 'bold'})
                        ])
                    ], style={'margin': '10px', 'padding': '15px', 'backgroundColor': '#f0f0f0', 'borderRadius': '10px', 
                              'width': '25%', 'display': 'inline-block', 'verticalAlign': 'top', 'textAlign': 'center'})
                ], style={'display': 'flex', 'justifyContent': 'space-between'}),
                
                # Heater control panel - now below temperature gauge
                html.Div([
                    html.P("Control:", style={'fontSize': '20px', 'fontWeight': 'bold', 'marginBottom': '15px'}),
                    html.Div([
                        # Target temperature control - improved styling
                        html.Div([
                            html.P("Target Temperature:", style={'fontSize': '16px', 'fontWeight': 'bold', 'marginBottom': '8px'}),
                            html.Div([
                                dcc.Input(
                                    id="target-temp-input",
                                    type="number",
                                    value=DEFAULT_TARGET_TEMP,
                                    min=10,
                                    max=35,
                                    step=0.5,
                                    disabled=temp_control_disabled,  # Now uses dynamic disabled state
                                    style={
                                        'width': '120px', 
                                        'height': '40px', 
                                        'fontSize': '18px', 
                                        'textAlign': 'center',
                                        'borderRadius': '4px',
                                        'border': '2px solid #2196F3'
                                    }
                                ),
                                html.Button(
                                    "Set", 
                                    id="set-temp-button", 
                                    disabled=temp_control_disabled,  # Now uses dynamic disabled state
                                    style={
                                        'marginLeft': '10px',
                                        'height': '40px',
                                        'width': '60px',
                                        'fontSize': '16px',
                                        'backgroundColor': '#2196F3',
                                        'color': 'white',
                                        'border': 'none',
                                        'borderRadius': '4px',
                                        'cursor': 'pointer'
                                    }
                                )
                            ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'marginBottom': '10px'}),
                            html.Div([
                                html.P("Current Target: ", style={'fontSize': '16px', 'display': 'inline-block'}),
                                html.P(
                                    id="current-target-temp", 
                                    children=f"{target_temperature} °C", 
                                    style={
                                        'fontSize': '18px', 
                                        'fontWeight': 'bold', 
                                        'color': '#FF5722',
                                        'display': 'inline-block',
                                        'marginLeft': '5px'
                                    }
                                )
                            ], style={'textAlign': 'center'})
                        ], style={'display': 'inline-block', 'marginRight': '60px', 'verticalAlign': 'top', 'width': '300px'}),
                        
                        # Fan control slider - make it support disabled state
                        html.Div([
                            html.P("Fan Speed:", style={'fontSize': '16px', 'fontWeight': 'bold', 'marginBottom': '15px'}),
                            html.Div([
                                dcc.Slider(
                                    id='fan-speed-slider',
                                    min=0,
                                    max=100,
                                    step=5,
                                    value=fan_speed,
                                    disabled=fan_control_disabled,  # Now uses dynamic disabled state
                                    marks={
                                        0: {'label': 'Off', 'style': {'color': '#77b0b1', 'fontSize': '14px'}},
                                        25: {'label': '25%', 'style': {'fontSize': '14px'}},
                                        50: {'label': '50%', 'style': {'fontSize': '14px'}},
                                        75: {'label': '75%', 'style': {'fontSize': '14px'}},
                                        100: {'label': 'Max', 'style': {'fontSize': '14px'}}
                                    },
                                    className='fan-slider',
                                    tooltip={"placement": "bottom", "always_visible": True}
                                ),
                            ], style={'width': '350px', 'margin': '0 auto'}),
                            html.Div(
                                id=FAN_SPEED_OUTPUT_ID,  # Using the new unique ID
                                children=f'Current: {fan_speed}%', 
                                style={
                                    'marginTop': '15px',
                                    'fontWeight': 'bold',
                                    'fontSize': '18px',
                                    'color': 'purple'
                                }
                            )
                        ], style={'display': 'inline-block', 'width': '400px', 'verticalAlign': 'top'})

                    ], style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'flex-start', 'flexWrap': 'wrap'})
                ], id="control-panel", style={'margin': '10px', 'marginTop': '20px', 'padding': '20px', 
                                              'backgroundColor': '#f0f0f0', 'borderRadius': '10px', 
                                              'textAlign': 'center', 'display': 'none'})  # Added display: none
            ])
        ], style={'margin': '20px', 'padding': '15px', 'backgroundColor': '#f9f9f9', 'borderRadius': '10px'}),
        
        # Sensors Status Panel
        html.Div([
            html.H2("Sensors Status"),
            html.Div([
                # Heater status indicator - added here
                html.Div([
                    html.P("Heater Status:", style={'display': 'inline-block'}),
                    html.Div(id="heater-status", 
                             style={'height': '25px', 'width': '25px', 'borderRadius': '50%', 
                                    'backgroundColor': HEATER_OFF_COLOR, 'display': 'inline-block', 'margin': '0 10px', 'verticalAlign': 'middle'}),
                    html.P(id="heater-status-text", children="OFF", 
                           style={'display': 'inline-block', 'fontWeight': 'bold'})
                ], style={'display': 'inline-block', 'marginRight': '50px'}),
                
                # Movement sensor indicator
                html.Div([
                    html.P("Movement Sensor:", style={'display': 'inline-block'}),
                    html.Div(id="movement-status", 
                             style={'height': '25px', 'width': '25px', 'borderRadius': '50%', 
                                    'backgroundColor': SENSOR_OFF_COLOR, 'display': 'inline-block', 'margin': '0 10px', 'verticalAlign': 'middle'}),
                    html.P(id="movement-status-text", children="No Movement", 
                           style={'display': 'inline-block', 'fontWeight': 'bold'})
                ], style={'display': 'inline-block', 'marginRight': '50px'}),
                
                # Window sensor indicator
                html.Div([
                    html.P("Window Sensor:", style={'display': 'inline-block'}),
                    html.Div(id="window-status", 
                             style={'height': '25px', 'width': '25px', 'borderRadius': '50%', 
                                    'backgroundColor': SENSOR_OFF_COLOR, 'display': 'inline-block', 'margin': '0 10px', 'verticalAlign': 'middle'}),
                    html.P(id="window-status-text", children="Closed", 
                           style={'display': 'inline-block', 'fontWeight': 'bold'})
                ], style={'display': 'inline-block'})
            ], style={'textAlign': 'center', 'margin': '15px'})
        ], style={'margin': '20px', 'padding': '15px', 'backgroundColor': '#f9f9f9', 'borderRadius': '10px'}),
    ], id='hideable-content'),
    
    # Temperature history graph - This section will always be visible
    html.Div([
        html.H2("History"),
        
        # Temperature and Fan graph
        html.Div([
            dcc.Graph(id='temperature-graph'),
        ], style={'marginBottom': '15px'}),
        
        # Sensors graph
        html.Div([
            dcc.Graph(id='sensors-graph'),
        ]),
        
        # Add a range selector that will control both graphs
        html.Div([
            dcc.RangeSlider(
                id='time-range-slider',
                min=0,
                max=100,
                step=1,
                value=[0, 100],
                marks=None,
                updatemode='mouseup'  # Only trigger when mouse is released
            )
        ], style={'marginTop': '20px', 'marginBottom': '10px'}),
        
        # Store component to share x-axis ranges between graphs
        dcc.Store(id='x-range-store'),
        
        # Keep existing interval
        dcc.Interval(id='interval-component', interval=2000, n_intervals=0)  # Update every 2 seconds
    ], style={'margin': '20px', 'padding': '15px', 'backgroundColor': '#f9f9f9', 'borderRadius': '10px'})
])

# Current temperature callback with sensor state monitoring
@callback(
    [Output('heater-status', 'style'),
     Output('heater-status-text', 'children'),
     Output('movement-status', 'style'),
     Output('movement-status-text', 'children'),
     Output('window-status', 'style'),
     Output('window-status-text', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_current_temp(n):
    global ACTIVE_MODE, temp_control_disabled, fan_control_disabled
    
    # Store previous sensor states to detect changes
    prev_window_state = window_open
    prev_movement_state = movement_detected
    
    # First try to get data from the database
    use_random = USE_RANDOM_DATA
    if not use_random:
        if not fetch_latest_sensor_data():
            use_random = True
    
    # If database retrieval failed or we're using random data
    if use_random:
        # Update movement and window sensor states randomly
        is_movement = update_movement_sensor()
        is_window_open = update_window_sensor()
    else:
        # Use the values fetched from the database
        is_movement = movement_detected
        is_window_open = window_open
    
    # Track if any sensor state changed
    sensor_changed = (is_window_open != prev_window_state or 
                     is_movement != prev_movement_state)
    
    # Comprehensive mode selection logic with prioritization
    # Following the same priority rules as in prvisamjojkosemrsio.py
    old_mode = ACTIVE_MODE
    
    # Determine the appropriate mode based on current sensor states
    if is_window_open:
        # Window open always takes highest priority - safety first!
        new_mode = "OFF"
        if is_window_open != prev_window_state:
            print("SENSOR CHANGE: Window opened - switching to OFF mode")
    elif is_movement:
        # Movement detected - use Automatic mode for comfort
        if ACTIVE_MODE == "Low":
            new_mode = "Automatic"
            if is_movement != prev_movement_state:
                print("SENSOR CHANGE: Movement detected - switching from Low to Automatic mode")
        else:
            # Keep current mode if already in a higher priority mode
            new_mode = ACTIVE_MODE
    else:
        # No movement, no window open - consider energy saving
        if ACTIVE_MODE == "Automatic":
            # Only switch to Low mode if coming from Automatic
            # Don't change PID, MANUAL, or other modes
            new_mode = "Low"
            print("SENSOR CHANGE: No movement - switching to Low energy mode")
        else:
            # Keep current mode
            new_mode = ACTIVE_MODE
            
    # Special case: Don't override MANUAL or PID modes with automatic changes
    # unless it's a safety issue (window open)
    if not is_window_open and (ACTIVE_MODE == "PID" or ACTIVE_MODE == "Ručni"):
        new_mode = ACTIVE_MODE
    
    # Update the mode if changed
    if new_mode != ACTIVE_MODE:
        ACTIVE_MODE = new_mode
        print(f"Mode changed from {old_mode} to {ACTIVE_MODE}")
        
        # Update control states based on the new mode
        if ACTIVE_MODE == "PID":
            temp_control_disabled = False
            fan_control_disabled = True
        elif ACTIVE_MODE == "Automatic":
            temp_control_disabled = True
            fan_control_disabled = True
        elif ACTIVE_MODE == "Ručni":
            temp_control_disabled = True
            fan_control_disabled = False
        elif ACTIVE_MODE == "Low":
            temp_control_disabled = True
            fan_control_disabled = True
        elif ACTIVE_MODE == "OFF":
            temp_control_disabled = True
            fan_control_disabled = True
        
        # Log the mode change to database
        log_parameters_to_influxdb()
    
    # Process temperature data and update device state
    if temp_data['temperature']:
        current_temp = temp_data['temperature'][-1]
        
        # Update heater state based on current temperature
        is_heater_on = update_heater_state(current_temp)
        
        # Set heater status color and text
        heater_style = {
            'height': '25px', 
            'width': '25px', 
            'borderRadius': '50%', 
            'backgroundColor': HEATER_ON_COLOR if is_heater_on else HEATER_OFF_COLOR, 
            'display': 'inline-block',
            'margin': '0 10px',
            'verticalAlign': 'middle'
        }
        heater_text = "ON" if is_heater_on else "OFF"
        
        # Set movement status color and text
        movement_style = {
            'height': '25px', 
            'width': '25px', 
            'borderRadius': '50%', 
            'backgroundColor': SENSOR_ON_COLOR if is_movement else SENSOR_OFF_COLOR, 
            'display': 'inline-block',
            'margin': '0 10px',
            'verticalAlign': 'middle'
        }
        movement_text = "Detected" if is_movement else "No Movement"
        
        # Set window status color and text
        window_style = {
            'height': '25px', 
            'width': '25px', 
            'borderRadius': '50%', 
            'backgroundColor': SENSOR_ON_COLOR if is_window_open else SENSOR_OFF_COLOR, 
            'display': 'inline-block',
            'margin': '0 10px',
            'verticalAlign': 'middle'
        }
        window_text = "Open" if is_window_open else "Closed"
        
        # Always log current state to database, even if mode didn't change
        if sensor_changed:
            log_parameters_to_influxdb()
        
        return heater_style, heater_text, movement_style, movement_text, window_style, window_text
    
    # Default values if no temperature data
    default_style = {'height': '25px', 'width': '25px', 'borderRadius': '50%', 'backgroundColor': SENSOR_OFF_COLOR, 'display': 'inline-block', 'margin': '0 10px', 'verticalAlign': 'middle'}
    return default_style, "OFF", default_style, "No Movement", default_style, "Closed"

# Temperature gauge callback
@callback(
    Output('temp-gauge', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_temp_gauge(n):
    # Default temperature if no data
    temp = 22.0
    
    # Get latest temperature if available
    if temp_data['temperature']:
        temp = temp_data['temperature'][-1]
        # Update ranges based on the latest data
        calculate_dynamic_ranges()
    
    # Set bar color based on temperature
    if temp < TEMP_RANGE_COLD:
        bar_color = COLD_COLOR
    elif temp < TEMP_RANGE_COMFORTABLE:
        bar_color = COMFORTABLE_COLOR
    elif temp < TEMP_RANGE_WARM:
        bar_color = WARM_COLOR
    else:
        bar_color = HOT_COLOR
    
    # Create a gauge figure
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=temp,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={},  # Removed the Temperature title
        number={'suffix': "°C", 'font': {'size': 26}},
        gauge={
            'axis': {'range': [temp_display_min, temp_display_max], 'tickwidth': 1, 'tickcolor': "gray"},
            'bar': {'color': bar_color},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [temp_display_min, TEMP_RANGE_COLD], 'color': 'rgba(0, 0, 255, 0.1)'},
                {'range': [TEMP_RANGE_COLD, TEMP_RANGE_COMFORTABLE], 'color': 'rgba(0, 255, 0, 0.1)'},
                {'range': [TEMP_RANGE_COMFORTABLE, TEMP_RANGE_WARM], 'color': 'rgba(255, 165, 0, 0.1)'},
                {'range': [TEMP_RANGE_WARM, temp_display_max], 'color': 'rgba(255, 0, 0, 0.1)'}
            ],
            'threshold': {
                'line': {'color': 'red', 'width': 4},
                'thickness': 0.75,
                'value': target_temperature
            }
        }
    ))
    
    # Remove margins and make it compact
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        height=200,
        paper_bgcolor='rgba(0,0,0,0)',  # Transparent background
        plot_bgcolor='rgba(0,0,0,0)'    # Transparent plot area
    )
    
    return fig

# Combined fan speed callback - handles both gauge and text display
@callback(
    [Output('fan-gauge', 'figure'),
     Output(FAN_SPEED_OUTPUT_ID, 'children')],
    [Input('fan-speed-slider', 'value'),
     Input('interval-component', 'n_intervals')],
    prevent_initial_call=False
)
def update_fan_display(slider_value, n_intervals):
    """Update fan speed display and gauge when slider changes or on interval update"""
    global fan_speed
    
    # Check context to see what triggered this callback
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
    
    # If slider changed, update the global fan speed
    if trigger_id == 'fan-speed-slider' and slider_value is not None:
        fan_speed = slider_value
        
        # Update fan history
        current_time = datetime.now().strftime('%H:%M:%S')
        fan_history['time'].append(current_time)
        fan_history['speed'].append(slider_value)
        
        # Keep only recent history
        if len(fan_history['time']) > MAX_DATA_POINTS:
            fan_history['time'] = fan_history['time'][-MAX_DATA_POINTS:]
            fan_history['speed'] = fan_history['speed'][-MAX_DATA_POINTS:]
        
        # Store this fan speed for local use (since we can't save it in the database)
        print(f"Fan speed updated to: {fan_speed}%")
    
    # If this is an interval update, calculate the fan speed based on mode
    elif trigger_id == 'interval-component':
        # Only auto-update fan speed if not in manual mode and we have temperature data
        if ACTIVE_MODE != "Ručni" and temp_data['temperature']:
            # Calculate appropriate fan speed based on conditions
            calculated_speed = calculate_dynamic_fan_speed(
                temp_data['temperature'][-1],
                target_temperature,
                window_open,
                ACTIVE_MODE,
                fan_speed
            )
            
            # Only update if the calculated speed is different
            if calculated_speed != fan_speed:
                fan_speed = calculated_speed
                
                # Update fan history for significant changes (more than 5%)
                current_time = datetime.now().strftime('%H:%M:%S')
                fan_history['time'].append(current_time)
                fan_history['speed'].append(fan_speed)
                
                # Keep only recent history
                if len(fan_history['time']) > MAX_DATA_POINTS:
                    fan_history['time'] = fan_history['time'][-MAX_DATA_POINTS:]
                    fan_history['speed'] = fan_history['speed'][-MAX_DATA_POINTS:]
                
                print(f"Fan speed auto-updated to: {fan_speed}%")
    
    # Create the gauge figure for fan speed
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=fan_speed,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={},
        number={'suffix': "%", 'font': {'size': 26}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "gray"},
            'bar': {'color': 'purple'},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 25], 'color': 'rgba(128, 0, 128, 0.1)'},
                {'range': [25, 50], 'color': 'rgba(128, 0, 128, 0.2)'},
                {'range': [50, 75], 'color': 'rgba(128, 0, 128, 0.3)'},
                {'range': [75, 100], 'color': 'rgba(128, 0, 128, 0.4)'}
            ]
        }
    ))
    
    # Format the gauge layout
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        height=200,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    # Create text display
    fan_text = f'Current: {fan_speed}%'
    
    # Return both the gauge figure and text display
    return fig, fan_text

# Temperature graph callback - update to use database data first
@callback(
    [Output('temperature-graph', 'figure'),
     Output('x-range-store', 'data')],
    [Input('interval-component', 'n_intervals'),
     Input('time-range-slider', 'value'),
     Input('x-range-store', 'data'),
     Input('device-state', 'data')],
    prevent_initial_call=False
)
def update_temperature_graph(n, range_value, x_range_data, device_state):
    # Check if device is on
    is_device_on = device_state.get('on', True) if device_state else True
    
    # If device is off, show a simple "Device Off" message
    if not is_device_on:
        # Create a minimal figure with text
        fig = go.Figure()
        fig.add_annotation(
            text="Device is OFF",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=28, color="#f44336"),
        )
        fig.update_layout(
            height=350,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        # No need to update range data when device is off
        return fig, x_range_data or {}
    
    # Use random data only if explicitly set or if database retrieval fails
    use_random = USE_RANDOM_DATA
    
    # Try to query from InfluxDB if available and not using random data
    if client is not None and not use_random:
        try:
            # Query historical temperature data for the last hour - changed table to pi
            query = 'SELECT sensors_temp FROM pi WHERE time > now() - 1h'
            result = client.query(query)
            
            if result:
                # Process points from the result
                points = list(result.get_points())
                if points:
                    times = [point['time'] for point in points]
                    temperatures = [point['sensors_temp'] for point in points if point['sensors_temp'] is not None]
                    
                    if times and temperatures:
                        # Update local cache
                        temp_data['time'] = [t.split('T')[1].split('.')[0] for t in times[-MAX_DATA_POINTS:]]  # Format time
                        temp_data['temperature'] = temperatures[-MAX_DATA_POINTS:]
                    else:
                        use_random = True  # Fall back to random if no valid data
            else:
                use_random = True  # No results, fall back to random
            
            # Note: Fan speed data (ac_intensity) is no longer in the pi table
            # Using current values or defaults
        
            # Query historical window state data - changed table to pi
            window_query = 'SELECT window_open FROM pi WHERE time > now() - 1h'
            window_result = client.query(window_query)
            
            if window_result:
                window_points = list(window_result.get_points())
                if window_points:
                    window_times = [point['time'] for point in window_points]
                    window_states = [bool(int(point['window_open'])) for point in window_points 
                                    if point['window_open'] is not None]
                    
                    if window_times and window_states:
                        window_history['time'] = [t.split('T')[1].split('.')[0] for t in window_times[-MAX_DATA_POINTS:]]
                        window_history['state'] = [1 if state else 0 for state in window_states[-MAX_DATA_POINTS:]]
            
            # Query historical movement sensor data (presence field) - changed table to pi
            movement_query = 'SELECT presence FROM pi WHERE time > now() - 1h'
            movement_result = client.query(movement_query)
            
            if movement_result:
                movement_points = list(movement_result.get_points())
                if movement_points:
                    movement_times = [point['time'] for point in movement_points]
                    movement_states = [bool(int(point['presence'])) for point in movement_points 
                                      if point['presence'] is not None]
                    
                    if movement_times and movement_states:
                        movement_history['time'] = [t.split('T')[1].split('.')[0] for t in movement_times[-MAX_DATA_POINTS:]]
                        movement_history['state'] = [1 if state else 0 for state in movement_states[-MAX_DATA_POINTS:]
            ]
        except Exception as e:
            print(f"Error querying historical data: {e}")
            use_random = True  # Fall back to random on error
    
    # Generate random data if needed - FIXED: Always generate a new data point when using random data
    if use_random:  # Removed the condition len(temp_data['time']) < 2
        current_time = datetime.now().strftime('%H:%M:%S')
        # Generate a somewhat realistic temperature value
        if not temp_data['temperature']:
            # First datapoint
            temp = random.uniform(RANDOM_TEMP_MIN + 4, RANDOM_TEMP_MIN + 8)
        else:
            # Make small variations to previous temperature
            prev_temp = temp_data['temperature'][-1]
            temp = prev_temp + random.uniform(-RANDOM_VARIATION, RANDOM_VARIATION)
            temp = max(RANDOM_TEMP_MIN, min(RANDOM_TEMP_MAX, temp))  # Constrain between min-max
        
        temp_data['time'].append(current_time)
        temp_data['temperature'].append(temp)
        
        # Keep only most recent data points
        if len(temp_data['time']) > MAX_DATA_POINTS:
            temp_data['time'] = temp_data['time'][-MAX_DATA_POINTS:]
            temp_data['temperature'] = temp_data['temperature'][-MAX_DATA_POINTS:]
    
    # Update dynamic ranges after data is updated
    calculate_dynamic_ranges()
    
    # Check if this update is triggered by a range change
    ctx = dash.callback_context
    range_update = False
    if ctx.triggered and ctx.triggered[0]['prop_id'] in ['time-range-slider.value', 'x-range-store.data']:
        range_update = True
    
    # Create the graph
    fig = go.Figure()
    
    # Add temperature trace
    fig.add_trace(go.Scatter(
        x=temp_data['time'],
        y=temp_data['temperature'],
        mode='lines+markers',
        name='Temperature',
        line=dict(color='firebrick', width=3)
    ))
    
    # Add fan speed trace (if we have data)
    if fan_history['time']:
        fig.add_trace(go.Scatter(
            x=fan_history['time'],
            y=fan_history['speed'],
            mode='lines',
            name='Fan Speed',
            line=dict(color='purple', width=2),
            yaxis='y2'  # Use secondary Y-axis
        ))
    
    # Add target temperature reference line
    fig.add_shape(
        type="line",
        x0=0,
        y0=target_temperature,
        x1=1,
        y1=target_temperature,
        xref="paper",
        line=dict(
            color="red",
            width=2,
            dash="dash",
        ),
    )
    
    # Add annotation for target temperature
    fig.add_annotation(
        x=0.02,
        y=target_temperature,
        xref="paper",
        text=f"Target: {target_temperature}°C",
        showarrow=False,
        font=dict(color="red"),
        bgcolor="rgba(255, 255, 255, 0.7)"
    )
    
    # Set up the layout with dual Y-axis
    fig.update_layout(
        title=f"Temperature & Fan Speed {'(Random Data)' if use_random else ''}",
        xaxis_title='Time',
        yaxis=dict(
            title='Temperature (°C)',
            range=[temp_display_min, temp_display_max]
        ),
        yaxis2=dict(
            title='Fan Speed (%)',
            range=[0, 100],
            anchor="x",
            overlaying="y",
            side="right"
        ),
        height=350,
        legend=dict(orientation="h", y=-0.2)
    )
    
    # Apply synchronized range if available
    if range_update and x_range_data:
        fig.update_layout(xaxis=dict(range=x_range_data['range']))
    
    # Extract current x-axis range from the figure to share
    current_range = None
    if fig.layout.xaxis.range:
        current_range = fig.layout.xaxis.range
    
    return fig, {'range': current_range}

@callback(
    Output('sensors-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('x-range-store', 'data'),
     Input('device-state', 'data')],
    prevent_initial_call=False
)
def update_sensors_graph(n, x_range_data, device_state):
    # Check if device is on
    is_device_on = device_state.get('on', True) if device_state else True
    
    # If device is off, show a simple "Device Off" message
    if not is_device_on:
        # Create a minimal figure with text
        fig = go.Figure()
        fig.add_annotation(
            text="Device is OFF",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=28, color="#f44336"),
        )
        fig.update_layout(
            height=350,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig
    
    # Create the graph for sensor states
    fig = go.Figure()
    
    # Add heater state trace
    if heater_history['time']:
        fig.add_trace(go.Scatter(
            x=heater_history['time'],
            y=heater_history['state'],
            mode='lines',
            name='Heater',
            line=dict(color='orange', width=2),
            fill='tozeroy'
        ))
    
    # Add movement sensor trace
    if movement_history['time']:
        fig.add_trace(go.Scatter(
            x=movement_history['time'],
            y=movement_history['state'],
            mode='lines',
            name='Movement',
            line=dict(color='blue', width=2),
            fill='tozeroy'
        ))
    
    # Add window sensor trace
    if window_history['time']:
        fig.add_trace(go.Scatter(
            x=window_history['time'],
            y=window_history['state'],
            mode='lines',
            name='Window',
            line=dict(color='green', width=2),
            fill='tozeroy'
        ))
    
    fig.update_layout(
        title="Sensor States",
        xaxis_title='Time',
        yaxis=dict(
            title='State',
            range=[-0.1, 1.1],  # Give a bit of padding for binary states
            tickvals=[0, 1],
            ticktext=['Off', 'On']
        ),
        height=350,
        legend=dict(orientation="h", y=-0.2)
    )
    
    # Apply synchronized range if available
    if x_range_data and 'range' in x_range_data:
        fig.update_layout(xaxis=dict(range=x_range_data['range']))
    
    return fig

# Add callback for graph relayouts (zoom/pan) to synchronize ranges
@callback(
    Output('x-range-store', 'data', allow_duplicate=True),
    [Input('temperature-graph', 'relayoutData'),
     Input('sensors-graph', 'relayoutData')],
    [State('x-range-store', 'data')],
    prevent_initial_call=True
)
def sync_graph_ranges(temp_relayout, sensor_relayout, current_ranges):
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return dash.no_update
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    relayout_data = temp_relayout if trigger_id == 'temperature-graph' else sensor_relayout
    
    if relayout_data and ('xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data):
        new_range = [relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']]
        return {'range': new_range}
    
    # When autorange happens or other relayout events that don't affect range
    if relayout_data and 'autorange' in relayout_data or 'xaxis.autorange' in relayout_data:
        return {'range': None}  # Reset range to allow autorange
    
    return dash.no_update

# Update the slider callback to control the view range
@callback(
    Output('x-range-store', 'data', allow_duplicate=True),
    Input('time-range-slider', 'value'),
    prevent_initial_call=True
)
def update_time_range(slider_range):
    if not temp_data['time'] or len(temp_data['time']) < 2:
        return dash.no_update
    
    # Convert slider 0-100 range to indices in the time array
    min_idx = int((slider_range[0]/100) * (len(temp_data['time'])-1))
    max_idx = int((slider_range[1]/100) * (len(temp_data['time'])-1))
    
    # Make sure we have valid indices
    min_idx = max(0, min(min_idx, len(temp_data['time'])-1))
    max_idx = max(0, min(max_idx, len(temp_data['time'])-1))
    
    # Get the actual time values at these indices
    start_time = temp_data['time'][min_idx]
    end_time = temp_data['time'][max_idx]
    
    return {'range': [start_time, end_time]}

@callback(
    Output('time-range-slider', 'marks'),
    Input('interval-component', 'n_intervals')
)
def update_slider_marks(n):
    if not temp_data['time'] or len(temp_data['time']) < 2:
        return {}
    
    # Create marks at a few positions
    marks = {}
    data_length = len(temp_data['time'])
    
    # Add marks at start, 25%, 50%, 75% and end
    for i, pos in enumerate([0, 0.25, 0.5, 0.75, 1.0]):
        idx = min(int(pos * (data_length - 1)), data_length - 1)
        marks[i * 25] = {'label': temp_data['time'][idx]}
    
    return marks

# Replace toggle view callback with device on/off callback
@callback(
    [Output('device-state', 'data'),
     Output('device-power-button', 'children'),
     Output('device-power-button', 'style'),
     Output('device-status-indicator', 'style'),
     Output('hideable-content', 'style')],
    [Input('device-power-button', 'n_clicks')],
    [State('device-state', 'data')],
    prevent_initial_call=True
)
def toggle_device(n_clicks, current_state):
    global DEVICE_ON
    
    if n_clicks is None:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Toggle the device on/off state
    new_state = not current_state.get('on', True)
    DEVICE_ON = new_state
    
    # Set button text and style based on state
    button_text = "TURN OFF" if new_state else "TURN ON"
    button_style = {
        'float': 'right',
        'marginTop': '10px',
        'padding': '10px 20px',
        'backgroundColor': '#4CAF50' if new_state else '#f44336',  # Green when ON, Red when OFF
        'color': 'white',
        'border': 'none',
        'borderRadius': '4px',
        'cursor': 'pointer',
        'fontSize': '16px',
        'fontWeight': 'bold'
    }
    
    # Status indicator color
    indicator_style = {
        'height': '20px', 
        'width': '20px', 
        'borderRadius': '50%', 
        'backgroundColor': '#4CAF50' if new_state else '#f44336',  # Green when ON, Red when OFF
        'display': 'inline-block', 
        'marginLeft': '15px', 
        'verticalAlign': 'middle'
    }
    
    # Hide controls when device is off
    content_style = {'display': 'block'} if new_state else {'display': 'none'}
    
    # Log the device state change
    log_parameters_to_influxdb()
    
    return {'on': new_state}, button_text, button_style, indicator_style, content_style

# New function to log all parameters to InfluxDB - updated to work with pi table
def log_parameters_to_influxdb():
    """Log all current parameters to InfluxDB"""
    if client and not USE_RANDOM_DATA:
        try:
            current_time = datetime.now()
            
            # Calculate appropriate fan speed based on mode and temperature
            current_fan_speed = calculate_dynamic_fan_speed(
                temp_data['temperature'][-1] if temp_data['temperature'] else 22.0,
                target_temperature,
                window_open,
                ACTIVE_MODE,
                fan_speed
            )
            
            # Log the calculated fan speed locally even if we can't store it in DB
            if current_fan_speed != fan_speed:
                print(f"Fan speed calculated: {current_fan_speed}% (not stored in DB)")
            
            # Prepare data to log - using pi table structure (pi table doesn't have fan speed)
            points = [
                {
                    'measurement': 'pi',
                    'time': current_time,
                    'fields': {
                        'sensors_temp': temp_data['temperature'][-1] if temp_data['temperature'] else None,
                        'presence': int(movement_detected),
                        'window_open': int(window_open)
                    }
                }
            ]
            
            # Write points to InfluxDB
            client.write_points(points)
            print(f"Successfully logged parameters to pi table at {current_time}")
        except Exception as e:
            print(f"Error logging parameters to InfluxDB: {e}")

# New function to calculate fan speed based on mode and conditions
def calculate_dynamic_fan_speed(current_temp, target_temp, window_is_open, current_mode, current_fan):
    """Calculate appropriate fan speed based on mode and conditions"""
    
    # If window is open, always turn off fans
    if window_is_open:
        return 0
    
    # Mode-specific behavior
    if current_mode == "OFF":
        return 0
    elif current_mode == "Low":
        return 10  # Low constant speed (10%)
    elif current_mode == "Ručni":
        return current_fan  # Use user-set fan speed
    elif current_mode == "PID":
        # Simple PID-like control (proportional only for simplicity)
        delta = abs(current_temp - target_temp)
        pid_output = min(100, max(0, delta * 8.0))  # Simple P control with kp=8.0
        return pid_output
    else:  # Automatic mode
        # Simple 3-level fan control based on temperature difference
        delta = abs(current_temp - target_temp)
        if delta <= 2:
            return 25  # Low speed
        elif delta <= 5:
            return 60  # Medium speed
        else:
            return 100  # High speed

# Mode buttons callback - handles all mode buttons including Low and OFF
@callback(
    [Output('active-mode', 'children'),
     Output('target-temp-input', 'disabled'),
     Output('set-temp-button', 'disabled'),
     Output('fan-speed-slider', 'disabled'),
     Output('control-panel', 'style')],
    [Input('pid-mode-button', 'n_clicks'),
     Input('Ručni-mode-button', 'n_clicks'),
     Input('automatic-mode-button', 'n_clicks'),
     Input('low-mode-button', 'n_clicks'),
     Input('off-mode-button', 'n_clicks')],
    prevent_initial_call=True
)
def update_temperature_mode(pid_clicks, Ručni_clicks, automatic_clicks, low_clicks, off_clicks):
    global ACTIVE_MODE, temp_control_disabled, fan_control_disabled, target_temperature, fan_speed
    
    # Default control panel style
    control_panel_style = {
        'margin': '10px', 
        'marginTop': '20px', 
        'padding': '20px', 
        'backgroundColor': '#f0f0f0', 
        'borderRadius': '10px', 
        'textAlign': 'center',
        'display': 'block'  # Make sure the control panel is visible by default
    }
    
    # Determine which button was clicked
    ctx = dash.callback_context
    if not ctx.triggered:
        # No button clicked yet, return current state
        return ACTIVE_MODE, temp_control_disabled, temp_control_disabled, fan_control_disabled, control_panel_style
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    old_mode = ACTIVE_MODE
    
    # Set modes and disabled states based on button clicked
    if button_id == "pid-mode-button":
        ACTIVE_MODE = "PID"
        target_temperature = PID_TEMP
        temp_control_disabled = False
        fan_control_disabled = True
    
    elif button_id == "automatic-mode-button":
        ACTIVE_MODE = "Automatic"
        target_temperature = AUTOMATIC_TEMP
        temp_control_disabled = True
        fan_control_disabled = True
    
    elif button_id == "Ručni-mode-button":
        ACTIVE_MODE = "Ručni"
        # Keep current target temperature
        temp_control_disabled = True
        fan_control_disabled = False
        
    elif button_id == "low-mode-button":
        ACTIVE_MODE = "Low"
        temp_control_disabled = True
        fan_control_disabled = True
        
        # For Low mode, set fan speed immediately
        if old_mode != "Low":
            fan_speed = 10  # Low constant speed (10%)
            
            # Update fan history
            current_time = datetime.now().strftime('%H:%M:%S')
            fan_history['time'].append(current_time)
            fan_history['speed'].append(fan_speed)
            
            # Keep only recent history
            if len(fan_history['time']) > MAX_DATA_POINTS:
                fan_history['time'] = fan_history['time'][-MAX_DATA_POINTS:]
                fan_history['speed'] = fan_history['speed'][-MAX_DATA_POINTS:]
        
    elif button_id == "off-mode-button":
        ACTIVE_MODE = "OFF"
        temp_control_disabled = True
        fan_control_disabled = True
        # Hide control panel in OFF mode
        control_panel_style['display'] = 'none'
        
        # For OFF mode, set fan speed to 0 immediately
        fan_speed = 0
        
        # Update fan history
        current_time = datetime.now().strftime('%H:%M:%S')
        fan_history['time'].append(current_time)
        fan_history['speed'].append(fan_speed)
        
        # Keep only recent history
        if len(fan_history['time']) > MAX_DATA_POINTS:
            fan_history['time'] = fan_history['time'][-MAX_DATA_POINTS:]
            fan_history['speed'] = fan_history['speed'][-MAX_DATA_POINTS:]
    
    # Log the mode change to InfluxDB
    log_parameters_to_influxdb()
    
    return ACTIVE_MODE, temp_control_disabled, temp_control_disabled, fan_control_disabled, control_panel_style