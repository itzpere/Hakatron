import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import random

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
        "mode": "Normal", 
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
        "mode": "Power Saving", 
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
    # Update values to simulate changing data
    for device in devices:
        if device["type"] == "computer" and device["power"]:  # Only update if powered on
            device["temperature"] = round(device["temperature"] + random.uniform(-0.5, 0.5), 1)
            device["fan_speed"] = max(0, min(100, device["fan_speed"] + random.randint(-3, 3)))
            
            # Occasionally change mode
            if random.random() < 0.1:
                device["mode"] = random.choice(["Normal", "Performance", "Power Saving", "Silent"])
                
        # Update status based on power
        device["status"] = "online" if device["power"] else "offline"
        
        # If device is off, gradually decrease temperature
        if not device["power"] and device["temperature"] > 25:
            device["temperature"] = round(max(25, device["temperature"] - 0.3), 1)
            device["fan_speed"] = 0
    
    # Filter by type
    filtered_devices = devices
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
    
    # Update device power state
    for device in devices:
        if device["id"] == device_id:
            device["power"] = value
            break
    
    # Return the current value (as received) to maintain the switch state
    return value