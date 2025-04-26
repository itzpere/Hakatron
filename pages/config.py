import dash
from dash import dcc, html, callback
from dash.dependencies import Input, Output, State
import os
import json
import datetime

# Import device name from sensor page
from pages.sensor import DEVICE_NAME

# Register the page
dash.register_page(
    __name__, 
    path=f'/{DEVICE_NAME.lower()}/config', 
    title=f'{DEVICE_NAME} Configuration', 
    name=f'Configure {DEVICE_NAME}'
)

# Define the path for the configuration file
CONFIG_DIR = "/home/pere/Desktop/Hakatron/config"
CONFIG_FILE = f"{CONFIG_DIR}/{DEVICE_NAME.lower()}_config.json"

# Default configuration
DEFAULT_CONFIG = {
    "device_name": DEVICE_NAME,
    "refresh_rate": 2000,  # milliseconds
    "temperature_unit": "celsius",
    "last_modified": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# Function to load configuration
def load_config():
    try:
        # Create config directory if it doesn't exist
        os.makedirs(CONFIG_DIR, exist_ok=True)
        
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            # Create default config file
            save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return DEFAULT_CONFIG

# Function to save configuration
def save_config(config):
    try:
        # Update modification date
        config["last_modified"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create config directory if it doesn't exist
        os.makedirs(CONFIG_DIR, exist_ok=True)
        
        # Save the config
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving configuration: {e}")
        return False

# Define the layout
layout = html.Div([
    # Header
    html.H1(f"{DEVICE_NAME} Configuration", style={'textAlign': 'center'}),
    
    # Configuration Form
    html.Div([
        # Device Name
        html.Div([
            html.Label("Device Name:"),
            dcc.Input(id="config-device-name", type="text", value="", style={'width': '100%'}),
        ], style={'margin': '10px 0'}),
        
        # Refresh Rate
        html.Div([
            html.Label("Refresh Rate (ms):"),
            dcc.Slider(
                id='config-refresh-rate',
                min=500,
                max=10000,
                step=500,
                value=2000,
                marks={i: f'{i}' for i in range(1000, 11000, 1000)},
            ),
            html.Div(id='refresh-rate-output')
        ], style={'margin': '20px 0'}),
        
        # Temperature Unit
        html.Div([
            html.Label("Temperature Unit:"),
            dcc.RadioItems(
                id='config-temp-unit',
                options=[
                    {'label': 'Celsius (°C)', 'value': 'celsius'},
                    {'label': 'Fahrenheit (°F)', 'value': 'fahrenheit'}
                ],
                value='celsius',
                style={'margin': '10px 0'}
            )
        ], style={'margin': '10px 0'}),
        
        # Submit Button
        html.Div([
            html.Button('Save Configuration', id='config-submit', n_clicks=0,
                       style={'backgroundColor': '#007BFF', 'color': 'white', 'border': 'none', 
                              'padding': '10px 15px', 'borderRadius': '5px', 'cursor': 'pointer'}),
            html.Div(id='config-submit-output', style={'margin': '10px 0', 'color': 'green'})
        ], style={'margin': '20px 0', 'textAlign': 'center'}),
        
        # Back to Dashboard Link
        html.Div([
            html.A("Back to Dashboard", href=f"/{DEVICE_NAME.lower()}", style={
                'textDecoration': 'none',
                'color': 'white',
                'backgroundColor': '#28a745',
                'padding': '10px 15px',
                'borderRadius': '5px',
                'display': 'inline-block'
            })
        ], style={'margin': '20px 0', 'textAlign': 'center'})
    ], style={'maxWidth': '800px', 'margin': '0 auto', 'padding': '20px', 'backgroundColor': '#f9f9f9', 'borderRadius': '10px'})
])

# Callback to initialize form with current config
@callback(
    [
        Output('config-device-name', 'value'),
        Output('config-refresh-rate', 'value'),
        Output('config-temp-unit', 'value')
    ],
    Input('config-submit', 'n_clicks'),  # This is just a trigger for initial load
    prevent_initial_call=False
)
def initialize_form(_):
    config = load_config()
    return (
        config.get('device_name', DEVICE_NAME),
        config.get('refresh_rate', 2000),
        config.get('temperature_unit', 'celsius')
    )

# Display refresh rate value
@callback(
    Output('refresh-rate-output', 'children'),
    Input('config-refresh-rate', 'value')
)
def update_refresh_output(value):
    return f'Selected refresh rate: {value} ms'

# Save configuration
@callback(
    Output('config-submit-output', 'children'),
    Input('config-submit', 'n_clicks'),
    [
        State('config-device-name', 'value'),
        State('config-refresh-rate', 'value'),
        State('config-temp-unit', 'value')
    ],
    prevent_initial_call=True
)
def save_configuration(n_clicks, device_name, refresh_rate, temp_unit):
    if n_clicks > 0:
        config = {
            "device_name": device_name if device_name else DEVICE_NAME,
            "refresh_rate": refresh_rate,
            "temperature_unit": temp_unit
        }
        
        if save_config(config):
            return f"Configuration saved successfully at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            return "Error saving configuration"
