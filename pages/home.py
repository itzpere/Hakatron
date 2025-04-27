import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import random
from influxdb import InfluxDBClient
from datetime import datetime

# InfluxDB connection parameters
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
        password=INFLUXDB_PASSWORD,
        database=INFLUXDB_DATABASE
    )
    print("Successfully connected to InfluxDB")
except Exception as e:
    print(f"Failed to connect to InfluxDB: {e}")
    client = None

# Function to check if data is recent (within last 10 minutes)
def is_data_recent(timestamp_str):
    if not timestamp_str:
        return False
    try:
        # Parse InfluxDB timestamp format
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%fZ')
        now = datetime.now()
        # Check if timestamp is within last 10 minutes
        return (now - timestamp).total_seconds() < 600
    except Exception as e:
        print(f"Error parsing timestamp: {e}")
        return False

# Function to fetch latest sensor data from InfluxDB
def fetch_latest_sensor_data():
    if client is None:
        print("No database connection, using random data")
        return None, None
    
    try:
        # Get the latest temperature
        temp_result = client.query('SELECT LAST(sensors_temp) FROM pi')
        temp_value = None
        if temp_result:
            points = list(temp_result.get_points())
            if points and is_data_recent(points[0]['time']):
                temp_value = points[0]['last']
        
        # Get the latest fan speed
        fan_result = client.query('SELECT LAST(speed) FROM fan_speed')
        fan_value = None
        if fan_result:
            points = list(fan_result.get_points())
            if points and is_data_recent(points[0]['time']):
                fan_value = points[0]['last']
        
        return temp_value, fan_value
    
    except Exception as e:
        print(f"Error fetching sensor data: {e}")
        return None, None

# Function to fetch devices with live data from database
def fetch_devices():
    # Start with the hardcoded devices as a base
    current_devices = devices.copy()
    
    # If no database connection, return the hardcoded values
    if client is None:
        print("No database connection, using hardcoded device data")
        return current_devices
    
    try:
        # Get the latest temperature data
        temp_query = client.query("SELECT LAST(sensors_temp) FROM pi")
        temp_points = list(temp_query.get_points())
        
        # Debug the temperature data
        print(f"Temperature data from database: {temp_points}")
        
        # Process temperature data without checking if recent
        if temp_points and len(temp_points) > 0:
            try:
                temp_value = round(float(temp_points[0]['last']), 1)
                print(f"Retrieved temperature: {temp_value}°C")
                
                # Apply to the pi device
                for device in current_devices:
                    if device["id"] == "pi":
                        print(f"Setting temperature for pi device: {temp_value}°C")
                        device["temperature"] = temp_value
            except (KeyError, ValueError) as e:
                print(f"Error processing temperature: {e}")
        
        # Get the latest fan speed
        fan_query = client.query("SELECT LAST(speed) FROM fan_speed")
        fan_points = list(fan_query.get_points())
        if fan_points:
            try:
                fan_speed = int(fan_points[0]['last'])
                # Apply to the pi device
                for device in current_devices:
                    if device["id"] == "pi":
                        device["fan_speed"] = fan_speed
            except (KeyError, ValueError) as e:
                print(f"Error processing fan speed: {e}")
        
        # Get power state for the pi device
        power_query = client.query("SELECT LAST(power) FROM device_info")
        power_points = list(power_query.get_points())
        if power_points:
            try:
                power_value = bool(power_points[0]['last'])
                # Apply to the pi device
                for device in current_devices:
                    if device["id"] == "pi":
                        device["power"] = power_value
                        # Update status based on power
                        device["status"] = "online" if power_value else "offline"
            except (KeyError, ValueError) as e:
                print(f"Error processing power state: {e}")
        
        # Get mode setting
        mode_query = client.query("SELECT LAST(mode) FROM device_settings")
        mode_points = list(mode_query.get_points())
        if mode_points:
            try:
                mode_value = mode_points[0]['last']
                # Apply to the pi device
                for device in current_devices:
                    if device["id"] == "pi":
                        device["mode"] = mode_value
            except (KeyError, ValueError) as e:
                print(f"Error processing mode: {e}")
        
        # Check if the pi device has temperature and fan_speed
        for device in current_devices:
            if device["id"] == "pi":
                if "temperature" not in device:
                    device["temperature"] = 25.0  # Default value
                if "fan_speed" not in device:
                    device["fan_speed"] = 0  # Default value
                
        return current_devices
        
    except Exception as e:
        print(f"Error fetching devices from database: {e}")
        import traceback
        traceback.print_exc()
        return current_devices  # Use hardcoded devices as fallback

# Alert data at the top for easier database integration
alerts = [
    {
        "id": "alert_001",
        "device_id": "raspberry_pi_b3plus",
        "type": "warning",
        "message": "High temperature detected",
        "timestamp": "2023-10-28 14:35:22",
        "acknowledged": False
    },
    {
        "id": "alert_002",
        "device_id": "demo_device",
        "type": "info",
        "message": "Fan speed reduced",
        "timestamp": "2023-10-28 13:12:05",
        "acknowledged": True
    }
]

# Device data at the top for easier database integration
# Raspberry Pi device and a Demo device
devices = [
    {
        "id": "pi", 
        "name": "Raspberry Pi B3+", 
        "type": "computer", 
        "status": "online", 
        "temperature": 42.3, 
        "fan_speed": 65,
        "mode": "Automatic", 
        "location": "Home Office",
        "power": True  # Device is powered on
    },
    {
        "id": "demo", 
        "name": "Demo", 
        "type": "computer", 
        "status": "online", 
        "temperature": 38.5, 
        "fan_speed": 45,
        "mode": "Automatic", 
        "location": "Lab",
        "power": True  # Device is powered on
    }
]

# Register the page
dash.register_page(__name__, path='/', title='Raspberry Pi', name='Raspberry Pi')

# Create a card for each device
def create_device_card(device):
    # Set color based on status
    status_color = "success" if device["status"] == "online" else "danger"
    
    # Choose icon based on device type
    icons = {
        "temperature": "🌡️",
        "humidity": "💧",
        "motion": "👁️",
        "light": "💡",
        "computer": "🖥️",
        "default": "📱"
    }
    icon = icons.get(device["type"], icons["default"])
    
    # Create a smaller card with temperature, fan speed %, and mode
    return dbc.Card([
        dbc.CardHeader([
            html.Span(f"{icon} {device['name']}", style={"fontWeight": "bold"}),
            html.Span(
                device["status"].capitalize(), 
                className=f"badge bg-{status_color} float-end"
            )
        ]),
        dbc.CardBody([
            html.Div([
                html.H5(f"Temperature: {device['temperature']} °C", className="mb-2"),
                html.H5(f"Fan Speed: {device['fan_speed']}%", className="mb-2"),
                html.H5(f"Mode: {device['mode']}", className="mb-2"),
                # Button row with power switch and details button
                html.Div([
                    # Power toggle switch
                    dbc.Switch(
                        id={"type": "device-power-switch", "index": device["id"]},
                        label="Power",
                        value=device["power"],
                        className="me-2"
                    ),
                    dbc.Button("View Details", color="primary", size="sm", href=f"/{device['id']}"),
                ], className="d-flex align-items-center justify-content-between")
            ], style={"padding": "0px"})
        ], style={"padding": "1rem"})
    ], className="mb-4 mx-auto", style={"max-width": "350px", "width": "100%"})

# Create an "Add Device" card with outline and plus sign
def create_add_device_card():
    card = dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className="fas fa-plus fa-3x", style={"color": "#cccccc"}),
                html.H5("Add Device", className="mt-3", style={"color": "#777777"})
            ], className="d-flex flex-column align-items-center justify-content-center", 
               style={"height": "100%"})
        ])
    ], className="mb-4", style={  # Removed mx-auto from here
        "width": "100%",
        "height": "200px", 
        "border": "2px dashed #cccccc", 
        "background-color": "#f8f9fa",
        "cursor": "pointer",
        "transition": "background-color 0.3s, border-color 0.3s"
    }, outline=True)
    
    # Wrap the card with a link that has proper width styling
    return html.A(
        card,
        href="/add-device",
        style={
            "textDecoration": "none", 
            "display": "block",
            "width": "100%", 
            "maxWidth": "350px"  # Match the max-width of device cards
        },
        className="add-device-link mx-auto",  # Added mx-auto here
        id="add-device-link"
    )

# Layout for the home page
layout = html.Div([
    html.H1("All devices", className="mb-4"),
    
    # Summary cards
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{len(devices)}", className="card-title text-center"),
                html.P("Total Devices", className="card-text text-center")
            ])
        ]), width=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{len([d for d in devices if d['status'] == 'online'])}", 
                      className="card-title text-center text-success"),
                html.P("Online", className="card-text text-center")
            ])
        ]), width=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{len([d for d in devices if d['status'] == 'offline'])}", 
                      className="card-title text-center text-danger"),
                html.P("Offline", className="card-text text-center")
            ])
        ]), width=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{len(alerts)}", className="card-title text-center text-warning"),
                html.P("Alerts", className="card-text text-center")
            ])
        ]), width=3),
    ], className="mb-4"),
    
    # Filter controls (keeping for structure, but less relevant with only one device)
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Label("Filter by type:"),
                dcc.Dropdown(
                    id="type-filter",
                    options=[
                        {"label": "All Types", "value": "all"},
                        {"label": "Computer", "value": "computer"},
                    ],
                    value="all"
                )
            ], className="mb-3")
        ], width=4),
        dbc.Col([
            html.Div([
                html.Label("Filter by status:"),
                dcc.Dropdown(
                    id="status-filter",
                    options=[
                        {"label": "All Statuses", "value": "all"},
                        {"label": "Online", "value": "online"},
                        {"label": "Offline", "value": "offline"},
                    ],
                    value="all"
                )
            ], className="mb-3")
        ], width=4),
        dbc.Col([
            html.Div([
                html.Label("Sort by:"),
                dcc.Dropdown(
                    id="sort-option",
                    options=[
                        {"label": "Name", "value": "name"},
                        {"label": "Location", "value": "location"},
                        {"label": "Status", "value": "status"},
                    ],
                    value="name"
                )
            ], className="mb-3")
        ], width=4),
    ]),
    
    # Device cards container
    html.Div(id="device-cards", children=[
        dbc.Row([
            # Raspberry Pi device
            dbc.Col(create_device_card(devices[0]), width=12, md=6, lg=4, className="mb-4 d-flex justify-content-center"),
            # Demo device
            dbc.Col(create_device_card(devices[1]), width=12, md=6, lg=4, className="mb-4 d-flex justify-content-center"),
            # Add new device card
            dbc.Col(create_add_device_card(), width=12, md=6, lg=4, className="mb-4 d-flex justify-content-center"),
        ], justify="center", className="g-4")
    ], className="px-4"),
    
    # Interval component to update data
    dcc.Interval(id="home-interval", interval=5000)
])

# Callback to filter and sort devices
@callback(
    Output("device-cards", "children"),
    [Input("type-filter", "value"),
     Input("status-filter", "value"),
     Input("sort-option", "value"),
     Input("home-interval", "n_intervals")]
)
def update_device_cards(type_filter, status_filter, sort_option, n_intervals):
    # Get devices from database
    current_devices = fetch_devices()
    
    # Update values for devices that don't have live data
    for device in current_devices:
        # If device is off, gradually decrease temperature
        if not device["power"] and device["temperature"] > 25:
            device["temperature"] = round(max(25, device["temperature"] - 0.3), 1)
            device["fan_speed"] = 0
    
    # Filter by type
    filtered_devices = current_devices
    if type_filter != "all":
        filtered_devices = [d for d in filtered_devices if d["type"] == type_filter]
    
    # Filter by status
    if status_filter != "all":
        filtered_devices = [d for d in filtered_devices if d["status"] == status_filter]
    
    # Sort
    filtered_devices = sorted(filtered_devices, key=lambda d: d[sort_option])
    
    # Create cards in grid layout
    device_columns = [
        dbc.Col(create_device_card(device), width=12, md=6, lg=4, className="mb-4 d-flex justify-content-center")
        for device in filtered_devices
    ]
    
    # Always add the "Add Device" card at the end
    device_columns.append(
        dbc.Col(create_add_device_card(), width=12, md=6, lg=4, className="mb-4 d-flex justify-content-center")
    )
    
    # Occasionally generate a new alert
    if random.random() < 0.05:  # 5% chance each update
        if filtered_devices:  # Make sure there are devices
            device = random.choice(filtered_devices)
            if device["power"] and device["temperature"] > 45:  # Only generate alerts for powered on devices
                new_alert = {
                    "id": f"alert_{len(alerts) + 1:03d}",
                    "device_id": device["id"],
                    "type": "warning",
                    "message": f"High temperature detected on {device['name']}",
                    "timestamp": "Now",
                    "acknowledged": False
                }
                if not any(a["device_id"] == device["id"] and a["type"] == "warning" and not a["acknowledged"] for a in alerts):
                    alerts.append(new_alert)
    
    return dbc.Row(device_columns, justify="center", className="g-4")

# Callback to handle power toggle switch changes
@callback(
    Output({"type": "device-power-switch", "index": dash.dependencies.MATCH}, "value"),
    Input({"type": "device-power-switch", "index": dash.dependencies.MATCH}, "value"),
    State({"type": "device-power-switch", "index": dash.dependencies.MATCH}, "id")
)
def toggle_device_power(value, id):
    # Find the device with matching ID
    device_id = id["index"]
    
    try:
        # Update power state in database
        if client:
            # Write the new power state to the database
            json_body = [
                {
                    "measurement": "device_info",
                    "tags": {
                        "device_id": device_id
                    },
                    "fields": {
                        "power": value
                    }
                }
            ]
            client.write_points(json_body)
    except Exception as e:
        print(f"Error updating device power in database: {e}")
    
    # Return the current value to maintain the switch state
    return value