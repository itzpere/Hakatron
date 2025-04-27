import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime
from influxdb import InfluxDBClient
import pandas as pd

# Register the page
dash.register_page(__name__, path='/add-device', title='Add Device', name='Add Device')

# Define all configuration variables from your prompt
DEVICE_NAME = "pi"
USE_RANDOM_DATA = False
RANDOM_TEMP_MIN = 18
RANDOM_TEMP_MAX = 30
RANDOM_VARIATION = 0.5
MAX_DATA_POINTS = 100
DEVICE_ON = True
PID_TEMP = 22
AUTOMATIC_TEMP = 22
ACTIVE_MODE = "OFF"
DEFAULT_TARGET_TEMP = 22
TEMP_HYSTERESIS = 0.5
INFLUXDB_URL = "10.147.18.192"
INFLUXDB_PORT = 8086
INFLUXDB_USER = "admin"
INFLUXDB_PASSWORD = "mia"
INFLUXDB_DATABASE = "mydb"

# Define sensor probabilities - moved from below to fix the NameError
MOVEMENT_PROBABILITY = 0.1
WINDOW_PROBABILITY = 0.05

# Device types with icons for selection
DEVICE_TYPES = [
    {"value": "computer", "label": "🖥️ Computer/IoT Device"},
    {"value": "temperature", "label": "🌡️ Temperature Sensor"},
    {"value": "humidity", "label": "💧 Humidity Sensor"},
    {"value": "motion", "label": "👁️ Motion Detector"},
    {"value": "window", "label": "🪟 Window Sensor"},
    {"value": "light", "label": "💡 Light Controller"}
]

# Location options
LOCATIONS = [
    "Living Room", "Kitchen", "Bedroom", "Office", 
    "Bathroom", "Hallway", "Garage", "Basement"
]

# Mode options
MODE_OPTIONS = [
    {"value": "OFF", "label": "Off"},
    {"value": "Automatic", "label": "Automatic"},
    {"value": "PID", "label": "PID Control"}
]

# Layout for the add device page
layout = html.Div([
    html.Div([
        html.H1("Add New Device", className="mb-4"),
        html.P("Set up a new device in your IoT system", className="text-muted mb-4"),
        
        # Device setup form
        dbc.Form([
            # Basic info section
            html.Div([
                html.H4("Basic Information", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Device Name", html_for="device-name"),
                        dbc.Input(
                            id="device-name",
                            type="text",
                            placeholder="Enter device name",
                            value="",
                            className="mb-3"
                        ),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Device ID", html_for="device-id"),
                        dbc.Input(
                            id="device-id",
                            type="text",
                            placeholder="Device ID (generated)",
                            value="",
                            disabled=True,
                            className="mb-3"
                        ),
                    ], width=6),
                ]),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Device Type", html_for="device-type"),
                        dcc.Dropdown(
                            id="device-type",
                            options=DEVICE_TYPES,
                            value="computer",
                            className="mb-3"
                        ),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Location", html_for="device-location"),
                        dcc.Dropdown(
                            id="device-location",
                            options=[{"label": loc, "value": loc} for loc in LOCATIONS],
                            value="Living Room",
                            className="mb-3"
                        ),
                    ], width=6),
                ]),
            ], className="mb-4 p-3 border rounded"),
            
            # Temperature settings section
            html.Div([
                html.H4("Temperature & Fan Control", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Control Mode", html_for="control-mode"),
                        dcc.Dropdown(
                            id="control-mode",
                            options=MODE_OPTIONS,
                            value=ACTIVE_MODE,
                            className="mb-3"
                        ),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Target Temperature (°C)", html_for="target-temp"),
                        dbc.Input(
                            id="target-temp",
                            type="number",
                            min=15,
                            max=30,
                            step=0.5,
                            value=DEFAULT_TARGET_TEMP,
                            disabled=ACTIVE_MODE != "PID",
                            className="mb-3"
                        ),
                    ], width=6),
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Temperature Hysteresis (°C)", html_for="temp-hysteresis"),
                        dbc.Input(
                            id="temp-hysteresis",
                            type="number",
                            min=0.1,
                            max=2.0,
                            step=0.1,
                            value=TEMP_HYSTERESIS,
                            disabled=ACTIVE_MODE != "PID",
                            className="mb-3"
                        ),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Initial Fan Speed (%)", html_for="fan-speed"),
                        dbc.Input(
                            id="fan-speed",
                            type="number",
                            min=0,
                            max=100,
                            step=5,
                            value=0,
                            className="mb-3"
                        ),
                    ], width=6),
                ]),
            ], id="temperature-settings", className="mb-4 p-3 border rounded"),
            
            # Sensor settings section
            html.Div([
                html.H4("Sensor Configuration", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Motion Detection"),
                        dbc.Switch(
                            id="motion-sensor-enabled",
                            label="Enable Motion Sensor",
                            value=False,
                            className="mb-3"
                        ),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Window Sensor"),
                        dbc.Switch(
                            id="window-sensor-enabled",
                            label="Enable Window Sensor",
                            value=False,
                            className="mb-3"
                        ),
                    ], width=6),
                ]),
                
                # Only show these options if the corresponding sensors are enabled
                html.Div([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Motion Detection Probability (%)"),
                            dbc.Input(
                                id="motion-probability",
                                type="number",
                                min=0,
                                max=100,
                                step=5,
                                value=int(MOVEMENT_PROBABILITY * 100),
                                disabled=False,
                                className="mb-3"
                            ),
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Window State Change Probability (%)"),
                            dbc.Input(
                                id="window-probability",
                                type="number",
                                min=0,
                                max=100,
                                step=5,
                                value=int(WINDOW_PROBABILITY * 100),
                                disabled=False,
                                className="mb-3"
                            ),
                        ], width=6),
                    ])
                ], id="sensor-probabilities-container"),
            ], id="sensor-settings", className="mb-4 p-3 border rounded"),
            
            # Database connection settings
            html.Div([
                html.H4("Database Connection", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("InfluxDB URL", html_for="influxdb-url"),
                        dbc.Input(
                            id="influxdb-url",
                            type="text",
                            value=INFLUXDB_URL,
                            className="mb-3"
                        ),
                    ], width=8),
                    dbc.Col([
                        dbc.Label("Port", html_for="influxdb-port"),
                        dbc.Input(
                            id="influxdb-port",
                            type="number",
                            value=INFLUXDB_PORT,
                            className="mb-3"
                        ),
                    ], width=4),
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Database Name", html_for="influxdb-database"),
                        dbc.Input(
                            id="influxdb-database",
                            type="text",
                            value=INFLUXDB_DATABASE,
                            className="mb-3"
                        ),
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Username", html_for="influxdb-user"),
                        dbc.Input(
                            id="influxdb-user",
                            type="text",
                            value=INFLUXDB_USER,
                            className="mb-3"
                        ),
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Password", html_for="influxdb-password"),
                        dbc.Input(
                            id="influxdb-password",
                            type="password",
                            value=INFLUXDB_PASSWORD,
                            className="mb-3"
                        ),
                    ], width=4),
                ]),
                dbc.Button("Test Connection", id="test-db-connection", color="secondary", className="me-2"),
                html.Span(id="connection-status", className="ms-2"),
            ], className="mb-4 p-3 border rounded"),
            
            # Form actions
            html.Div([
                dbc.Button("Add Device", id="add-device-button", color="primary", className="me-2"),
                dbc.Button("Cancel", href="/", color="secondary"),
                # Success message (hidden by default)
                html.Div(id="success-message", className="mt-3")
            ], className="d-flex justify-content-between align-items-center"),
        ])
    ], className="container py-4")
])

# Callback to generate device ID based on name
@callback(
    Output("device-id", "value"),
    Input("device-name", "value")
)
def generate_device_id(name):
    if not name:
        return ""
    # Generate a simple ID based on the name (lowercase with underscores)
    device_id = name.lower().replace(" ", "_")
    # Add a timestamp to make it unique
    timestamp = datetime.now().strftime("%m%d%H%M")
    return f"{device_id}_{timestamp}"

# Callback to toggle input fields based on control mode
@callback(
    [Output("target-temp", "disabled"),
     Output("temp-hysteresis", "disabled")],
    Input("control-mode", "value")
)
def update_temperature_controls(mode):
    # If mode is PID, enable these controls, otherwise disable
    disabled = mode != "PID"
    return disabled, disabled

# Callback to show/hide sensor probability fields
@callback(
    [Output("motion-probability", "disabled"),
     Output("window-probability", "disabled")],
    [Input("motion-sensor-enabled", "value"),
     Input("window-sensor-enabled", "value")]
)
def update_sensor_probabilities(motion_enabled, window_enabled):
    return not motion_enabled, not window_enabled

# Callback to test database connection
@callback(
    Output("connection-status", "children"),
    Input("test-db-connection", "n_clicks"),
    [State("influxdb-url", "value"),
     State("influxdb-port", "value"),
     State("influxdb-database", "value"),
     State("influxdb-user", "value"),
     State("influxdb-password", "value")],
    prevent_initial_call=True
)
def test_connection(n_clicks, url, port, database, username, password):
    if n_clicks is None:
        return ""
    
    try:
        client = InfluxDBClient(
            host=url,
            port=port,
            username=username,
            password=password
        )
        client.switch_database(database)
        # Try to perform a simple query
        result = client.query('SHOW MEASUREMENTS LIMIT 1')
        return html.Span("Connection successful! ✓", style={"color": "green", "fontWeight": "bold"})
    except Exception as e:
        return html.Span(f"Connection failed: {str(e)}", style={"color": "red"})

# Callback for adding the device
@callback(
    Output("success-message", "children"),
    Input("add-device-button", "n_clicks"),
    [State("device-name", "value"),
     State("device-id", "value"),
     State("device-type", "value"),
     State("device-location", "value"),
     State("control-mode", "value"),
     State("target-temp", "value"),
     State("fan-speed", "value"),
     State("motion-sensor-enabled", "value"),
     State("window-sensor-enabled", "value"),
     State("influxdb-url", "value"),
     State("influxdb-port", "value"),
     State("influxdb-database", "value"),
     State("influxdb-user", "value"),
     State("influxdb-password", "value")],
    prevent_initial_call=True
)
def add_device(n_clicks, name, device_id, device_type, location, control_mode, 
               target_temp, fan_speed, motion_enabled, window_enabled,
               db_url, db_port, db_name, db_user, db_password):
    if n_clicks is None:
        return ""
    
    if not name or not device_id:
        return html.Div("Please enter a device name.", style={"color": "red"})
    
    try:
        # Connect to InfluxDB
        client = InfluxDBClient(
            host=db_url,
            port=db_port,
            username=db_user,
            password=db_password
        )
        client.switch_database(db_name)
        
        # Create device record in database
        current_time = datetime.now().isoformat()
        
        # Device info point
        device_info = [
            {
                "measurement": "device_info",
                "tags": {
                    "device_id": device_id,
                    "device_type": device_type
                },
                "fields": {
                    "name": name,
                    "location": location,
                    "power": True  # Default to powered on
                }
            }
        ]
        
        # Device settings point
        device_settings = [
            {
                "measurement": "device_settings",
                "tags": {
                    "device_id": device_id
                },
                "fields": {
                    "mode": control_mode,
                    "target_temp": float(target_temp),
                    "fan_speed": int(fan_speed),
                    "motion_enabled": bool(motion_enabled),
                    "window_enabled": bool(window_enabled)
                }
            }
        ]
        
        # Write both points
        client.write_points(device_info)
        client.write_points(device_settings)
        
        # Success message with redirect
        return html.Div([
            dbc.Alert([
                html.H4("Success!", className="alert-heading"),
                html.P(f"Device '{name}' has been added to your system."),
                html.Hr(),
                html.P("You will be redirected to the devices page in a few seconds.", className="mb-0")
            ], color="success"),
            dcc.Location(id="redirect-home", pathname="/", refresh=True)
        ])
        
    except Exception as e:
        return html.Div(f"Error adding device: {str(e)}", style={"color": "red"})

# Callback for redirect after successful device addition
@callback(
    Output("redirect-home", "pathname"),
    Input("redirect-home", "pathname"),
    prevent_initial_call=True
)
def redirect_to_home(pathname):
    # Redirect to home page after 3 seconds
    return "/"