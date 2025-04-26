import dash
from dash import dcc, html, callback
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
from datetime import datetime
import random

# Define all configuration variables at the top
DEVICE_NAME = "pi"
USE_RANDOM_DATA = True  # Flag to control whether to use random data
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
INFLUXDB_URL = "10.147.18.192"
INFLUXDB_PORT = 8086
INFLUXDB_USER = "admin"
INFLUXDB_PASSWORD = "mia"
INFLUXDB_DATABASE = "mydb"

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

# Initialize InfluxDB client if available
client = None
if influxdb_available and not USE_RANDOM_DATA:
    try:
        client = InfluxDBClient(
            host=INFLUXDB_URL,
            port=INFLUXDB_PORT,
            username=INFLUXDB_USER,
            password=INFLUXDB_PASSWORD,
            database=INFLUXDB_DATABASE
        )
        print("Successfully connected to InfluxDB")
        
        # List all available databases
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
    except Exception as e:
        print(f"Database setup error: {e}")
        client = None
        USE_RANDOM_DATA = True
else:
    USE_RANDOM_DATA = True
    print("Using random data for temperature values")

# Define the layout for just this page (without the navbar which is in app.py)
layout = html.Div([
    # Store component to track device state (on/off)
    dcc.Store(id='device-state', data={'on': DEVICE_ON}),
    
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
                                        style={'width': '100%', 'padding': '10px',
                                              'backgroundColor': '#2196F3', 'color': 'white', 'border': 'none',
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
                                id='fan-speed-output', 
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

# Mode buttons callback - updated to also handle control states
@callback(
    [Output('active-mode', 'children'),
     Output('target-temp-input', 'value'),
     Output('current-target-temp', 'children'),
     Output('target-temp-input', 'disabled'),
     Output('set-temp-button', 'disabled'),
     Output('fan-speed-slider', 'disabled'),
     Output('target-temp-input', 'style'),
     Output('set-temp-button', 'style'),
     Output('control-panel', 'style')],  # Added this output
    [Input('pid-mode-button', 'n_clicks'),
     Input('Ručni-mode-button', 'n_clicks'),
     Input('automatic-mode-button', 'n_clicks')],
    prevent_initial_call=True
)
def update_temperature_mode(pid_clicks, Ručni_clicks, automatic_clicks):
    global target_temperature, ACTIVE_MODE, temp_control_disabled, fan_control_disabled
    
    # Default button styles
    input_style = {
        'width': '120px', 
        'height': '40px', 
        'fontSize': '18px', 
        'textAlign': 'center',
        'borderRadius': '4px',
        'border': '2px solid #2196F3'
    }
    
    button_style = {
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
    
    # Default control panel style
    control_panel_style = {
        'margin': '10px', 
        'marginTop': '20px', 
        'padding': '20px', 
        'backgroundColor': '#f0f0f0', 
        'borderRadius': '10px', 
        'textAlign': 'center'
    }
    
    # Determine which button was clicked using callback context
    ctx = dash.callback_context
    if not ctx.triggered:
        # No button clicked yet, return current state
        return (ACTIVE_MODE, target_temperature, f"{target_temperature} °C", 
                temp_control_disabled, temp_control_disabled, fan_control_disabled, 
                input_style, button_style, control_panel_style)
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Set modes and disabled states based on button clicked
    if button_id == "pid-mode-button":
        ACTIVE_MODE = "PID"
        target_temperature = PID_TEMP
        # PID mode: Enable temperature control, disable fan control
        temp_control_disabled = False
        fan_control_disabled = True
    
    elif button_id == "automatic-mode-button":
        ACTIVE_MODE = "Automatic"
        target_temperature = AUTOMATIC_TEMP
        # Automatic mode: Disable both controls and hide control panel
        temp_control_disabled = True
        fan_control_disabled = True
        control_panel_style['display'] = 'none'  # Hide the control panel
    
    elif button_id == "Ručni-mode-button":
        ACTIVE_MODE = "Ručni"
        # Keep current temperature
        # Ručni mode: Disable temperature control, enable fan control
        temp_control_disabled = True
        fan_control_disabled = False
    
    # Update styling for disabled state
    if temp_control_disabled:
        input_style.update({
            'backgroundColor': '#f0f0f0',
            'border': '2px solid #cccccc',
            'color': '#999999',
            'cursor': 'not-allowed'
        })
        button_style.update({
            'backgroundColor': '#cccccc',
            'color': '#666666',
            'cursor': 'not-allowed'
        })
    
    return (ACTIVE_MODE, 
            target_temperature, 
            f"{target_temperature} °C", 
            temp_control_disabled,
            temp_control_disabled, 
            fan_control_disabled,
            input_style,
            button_style,
            control_panel_style)  # Return the control panel style

# Target temperature setting callback - update to work with modes
@callback(
    [Output('current-target-temp', 'children', allow_duplicate=True)],
    [Input('set-temp-button', 'n_clicks')],
    [State('target-temp-input', 'value')],
    prevent_initial_call=True
)
def update_target_temperature(n_clicks, value):
    global target_temperature, ACTIVE_MODE
    if n_clicks is not None and value is not None:
        target_temperature = float(value)
        ACTIVE_MODE = "Ručni"  # Setting manual temperature always switches to Ručni mode
    return [f"{target_temperature} °C"]

# Current temperature callback - MODIFIED to remove current-temp output
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
        
        # Update movement and window sensor states
        is_movement = update_movement_sensor()
        is_window_open = update_window_sensor()
        
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
        
        # Remove temperature from return values
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

# Fan gauge callback
# 2. Update the callback definition
@callback(
    Output('fan-gauge', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_fan_gauge(n):
    # Create a gauge figure for fan speed
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
    
    # Remove margins and make it compact
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        height=200,
        paper_bgcolor='rgba(0,0,0,0)',  # Transparent background
        plot_bgcolor='rgba(0,0,0,0)'    # Transparent plot area
    )
    
    return fig  # Only return the figure, not the text

# Temperature graph callback - modify the existing function
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
    
    # Existing code for when device is on
    use_random = USE_RANDOM_DATA
    
    # Try to query from InfluxDB if available and if random data is not forced
    if client is not None and not USE_RANDOM_DATA:
        try:
            query = f'SELECT time, value FROM temperature WHERE time > now() - 1h'
            result = client.query(query)
            
            if result:
                # Process points from the result
                points = list(result.get_points())
                if points:
                    times = [point['time'] for point in points]
                    temperatures = [point['value'] for point in points]
                    
                    # Update local cache
                    temp_data['time'] = [t.split('T')[1].split('.')[0] for t in times[-MAX_DATA_POINTS:]]  # Format time
                    temp_data['temperature'] = temperatures[-MAX_DATA_POINTS:]
                    use_random = False
        except Exception as e:
            print(f"Error querying temperature data: {e}")
            use_random = True
    
    # Generate random data if needed
    if use_random:
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
    
    return {'on': new_state}, button_text, button_style, indicator_style, content_style

# Replace the update_fan_speed callback

@callback(
    Output('fan-speed-output', 'children'),
    Input('fan-speed-slider', 'value')
)
def update_fan_speed(value):
    global fan_speed, fan_history, ACTIVE_MODE
    
    # Update the global fan speed value
    fan_speed = value
    
    # Record fan speed history
    current_time = datetime.now().strftime('%H:%M:%S')
    fan_history['time'].append(current_time)
    fan_history['speed'].append(fan_speed)
    
    # Keep only recent history
    if len(fan_history['time']) > MAX_DATA_POINTS:
        fan_history['time'] = fan_history['time'][-MAX_DATA_POINTS:]
        fan_history['speed'] = fan_history['speed'][-MAX_DATA_POINTS:]
    
    # If we're in Ručni mode and connected to InfluxDB, send the update
    if ACTIVE_MODE == "Ručni" and client and not USE_RANDOM_DATA:
        try:
            # Write the fan speed setting to InfluxDB configuration
            point = {
                'measurement': 'config',
                'fields': {
                    'manual_speed': 1 if value <= 30 else 2 if value <= 70 else 3,
                    'fan_percentage': float(value)
                }
            }
            client.write_points([point])
        except Exception as e:
            print(f"Error updating fan speed in InfluxDB: {e}")
    
    return f'Current: {fan_speed}%'