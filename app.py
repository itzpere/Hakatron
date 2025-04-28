import dash
from dash import html, dcc, clientside_callback
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from influxdb import InfluxDBClient
import datetime
from alerts_logic import check_window_sensor
import random
from dash.exceptions import PreventUpdate

# Global variables for application state
alert_count = 0  # This will be dynamically updated from database

# InfluxDB Connection Parameters
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
    # Create the database if it doesn't exist
    if INFLUXDB_DATABASE not in [db['name'] for db in client.get_list_database()]:
        client.create_database(INFLUXDB_DATABASE)
    client.switch_database(INFLUXDB_DATABASE)
    print("Successfully connected to InfluxDB")
except Exception as e:
    print(f"Error initializing InfluxDB client: {e}")
    client = None

# Function to check if InfluxDB is available
def influxdb_available():
    if client is None:
        return False
    try:
        client.ping()
        return True
    except Exception as e:
        print(f"InfluxDB connection check failed: {e}")
        return False

# Alert management functions
def get_alerts(limit=100):
    """
    Retrieve alerts from InfluxDB - no fallback to sample data
    """
    if not influxdb_available():
        print("Database not available for retrieving alerts")
        return []  # Return empty list if DB is not available
    
    try:
        # Query recent alerts, ordered by time
        query = f'SELECT * FROM alerts ORDER BY time DESC LIMIT {limit}'
        result = client.query(query)
        
        # Convert InfluxDB results to our alert format
        alerts = []
        for point in result.get_points(measurement='alerts'):
            alert = {
                "id": point.get('alert_id', 0),
                "device": point.get('device', 'Unknown Device'),
                "message": point.get('message', 'No message'),
                "severity": point.get('severity', 'medium'),
                "time": point.get('time', '').split('.')[0].replace('T', ' ')  # Format timestamp
            }
            alerts.append(alert)
        
        return alerts  # Return whatever we found, even if empty
    except Exception as e:
        print(f"Error retrieving alerts: {e}")
        return []  # Return empty list on error

def add_alert(device, message, severity="medium"):
    """
    Add a new alert to InfluxDB
    """
    if not influxdb_available():
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

def count_alerts():
    """
    Count all alerts in the database
    """
    if not influxdb_available():
        print("Database not available for counting alerts")
        return 0  # Return 0 if DB is not available
    
    try:
        # Query to count alerts
        query = 'SELECT COUNT(*) FROM alerts'
        result = client.query(query)
        
        # Extract count value
        counts = list(result.get_points())
        if counts and len(counts) > 0:
            return counts[0].get('count', 0)
            
        return 0  # Return 0 if no count found
    except Exception as e:
        print(f"Error counting alerts: {e}")
        return 0  # Return 0 on error

# Initialize the Dash app
app = dash.Dash(__name__, 
                use_pages=True, 
                external_stylesheets=[dbc.themes.BOOTSTRAP],  # Dark industrial theme
                suppress_callback_exceptions=True)

# Define the common layout (navbar will appear on all pages)
app.layout = html.Div([
    # Interval component for periodic updates
    dcc.Interval(
        id='app-interval-component',
        interval=10*1000,  # 10 seconds
        n_intervals=0
    ),
    
    # Top panel / navigation bar
    html.Div([
        # Left section - Team name
        html.Div([
            html.H3("MIA - IoT", style={
                'margin': '0',
                'color': 'white',
                'fontWeight': 'bold'
            })
        ], style={'flex': '1'}),
        
        # Navigation links
        html.Div([
            dcc.Link("All Devices", href="/", style={
                'marginRight': '15px',
                'color': 'white',
                'textDecoration': 'none'
            }),
        ], style={'display': 'flex', 'alignItems': 'center'}),
        
        # Right section - Action buttons
        html.Div([
            # Alerts with dropdown
            html.Div([
                # Alerts button with notification dot
                html.Div([
                    html.Span("Alerts", style={
                        'color': 'white',
                        'marginRight': '5px' # Space between text and potential dot
                    }),
                    # Simple red notification dot (always visible)
                    html.Span(
                        id="alert-notification-dot",
                        style={
                            'position': 'absolute',
                            'top': '2px',  # Adjust position relative to "Alerts" text
                            'right': '-8px', # Adjust position relative to "Alerts" text
                            'width': '10px',
                            'height': '10px',
                            'backgroundColor': '#e74c3c', # Red color
                            'borderRadius': '50%',
                            'display': 'block' # Changed from 'none' to 'block'
                        }
                    )
                ], id="alerts-button", style={
                    'display': 'flex',
                    'alignItems': 'center',
                    'cursor': 'pointer',
                    'position': 'relative' # Needed for absolute positioning of the dot
                }),
                
                # Dropdown for alerts (hidden by default)
                html.Div([
                    # Alert items placeholder - will be populated by callback
                    html.Div(
                        id="alerts-content",
                        style={
                            'maxHeight': '400px',  # Increased height
                            'overflowY': 'auto',
                            'overflowX': 'hidden'  # Prevent horizontal scrolling
                        }
                    ),
                    
                    # View All Alerts button
                    html.Div([
                        dcc.Link(
                            "View All Alerts", 
                            href="/alerts", 
                            style={
                                'color': 'white',
                                'textDecoration': 'none',
                                'textAlign': 'center',
                                'width': '100%',
                                'display': 'block'
                            }
                        )
                    ], style={
                        'backgroundColor': '#2c3e50',
                        'padding': '10px',
                        'textAlign': 'center'
                    })
                ], style={
                    'width': '400px',  # Increased from 300px
                    'backgroundColor': 'white',
                    'boxShadow': '0 2px 10px rgba(0,0,0,0.2)',
                    'borderRadius': '4px',
                    'position': 'absolute',
                    'top': '45px',
                    'right': '0',
                    'zIndex': '1000',
                    'display': 'none'
                }, id="alerts-dropdown")
            ], style={
                'marginRight': '20px',
                'position': 'relative'
            }, id="alerts-container"),
            
            # Login button
            # Profile link with icon
            dcc.Link([
                html.I(className="fas fa-user-circle", style={"marginRight": "8px"}), 
                "Profile"
            ], href="/profile", style={
                'backgroundColor': '#4CAF50',
                'color': 'white',
                'border': 'none',
                'borderRadius': '4px',
                'padding': '6px 16px',
                'cursor': 'pointer',
                'fontWeight': 'bold',
                'textDecoration': 'none',
                'display': 'flex',
                'alignItems': 'center'
            })
        ], style={'display': 'flex', 'alignItems': 'center'})
    ], style={
        'display': 'flex',
        'justifyContent': 'space-between',
        'alignItems': 'center',
        'backgroundColor': '#2c3e50',
        'padding': '10px 20px',
        'marginBottom': '20px',
        'boxShadow': '0 2px 5px rgba(0,0,0,0.2)'
    }),
    
    # Add an invisible div to capture clicks outside the alerts dropdown
    html.Div(id="click-outside-detector", style={"position": "fixed", "top": 0, "left": 0, "width": "100%", "height": "100%", "zIndex": -1, "display": "none"}),
    
    # Page content - this is where the current page will be displayed
    html.Div(
        dash.page_container,
        style={
            'paddingLeft': '20px',
            'paddingRight': '20px'
        }
    ),
    
    # Hidden div to trigger window sensor checks
    html.Div(id="window-sensor-check-trigger", style={"display": "none"})
])

@app.callback(
    [Output('db-status', 'children'),
     Output('db-status-led', 'style')],
    Input('app-interval-component', 'n_intervals')
)
def update_db_status(n):
    base_led_style = {
        'width': '12px', 
        'height': '12px',
        'borderRadius': '50%',
        'display': 'inline-block',
        'cursor': 'pointer'
    }
    
    try:
        # Use our local function to check database availability
        db_available = influxdb_available()
        
        if db_available:
            # Connected - green LED
            led_style = base_led_style.copy()
            led_style['backgroundColor'] = '#4CAF50'  # Green
            led_style['boxShadow'] = '0 0 8px #4CAF50'  # Green glow
            return "Connected to Database ✓", led_style
        else:
            # Disconnected - amber/yellow LED
            led_style = base_led_style.copy()
            led_style['backgroundColor'] = '#F39C12'  # Amber
            led_style['boxShadow'] = '0 0 8px #F39C12'  # Amber glow
            return "Database Disconnected !", led_style
    except Exception as e:
        print(f"Error checking database status: {e}")
        # Error in check - red LED
        led_style = base_led_style.copy()
        led_style['backgroundColor'] = '#f44336'  # Red
        led_style['boxShadow'] = '0 0 8px #f44336'  # Red glow
        return "Error Checking Database ⚠️", led_style

# Update the alerts dropdown content with real data from the database
@app.callback(
    Output("alerts-content", "children"),
    Input("app-interval-component", "n_intervals")
)
def update_alerts_content(n):
    # Get fresh alerts from the database
    latest_alerts = get_alerts(limit=5)  # Show only 5 most recent alerts in dropdown
    
    # If no alerts, show a message
    if not latest_alerts:
        return html.Div([
            html.Div("No alerts found in database", style={
                'padding': '20px',
                'textAlign': 'center',
                'color': '#777'
            }),
            html.Div(f"Last checked: {datetime.datetime.now().strftime('%H:%M:%S')}", style={
                'fontSize': '11px',
                'textAlign': 'center',
                'color': '#999',
                'marginTop': '5px'
            })
        ])
    
    # Create header for database info
    header = html.Div([
        html.Div("Live Database Alerts", style={
            'fontWeight': 'bold',
            'padding': '8px 10px',
            'backgroundColor': '#f8f9fa',
            'borderBottom': '1px solid #eee',
            'color': '#2c3e50'
        }),
        html.Div(f"Last updated: {datetime.datetime.now().strftime('%H:%M:%S')}", style={
            'fontSize': '11px',
            'padding': '2px 10px 8px 10px',
            'backgroundColor': '#f8f9fa',
            'borderBottom': '1px solid #eee',
            'color': '#777'
        })
    ])
    
    # Create alert items with improved styling for readability
    alert_items = []
    for alert in latest_alerts:
        severity_color = '#e74c3c' if alert["severity"] == "high" else '#f39c12' if alert["severity"] == "medium" else '#3498db'
        alert_items.append(html.Div([
            html.Div([
                html.Strong(alert["device"], style={
                    'color': '#2c3e50',
                    'display': 'block',  # Make device name appear on its own line
                    'marginBottom': '3px'
                }),
                html.Span(alert["time"], style={
                    'fontSize': '12px', 
                    'color': '#777',
                    'display': 'block'  # Make timestamp appear on its own line
                })
            ]),
            html.Div(alert["message"], style={
                'color': '#555', 
                'marginTop': '5px',
                'marginBottom': '8px',
                'wordWrap': 'break-word',  # Ensure long messages wrap properly
                'whiteSpace': 'normal',    # Allow text to wrap
                'lineHeight': '1.4'        # Improve readability with line spacing
            }),
            html.Div(alert["severity"].capitalize(), style={
                'color': '#fff',
                'backgroundColor': severity_color,
                'padding': '2px 8px',
                'borderRadius': '3px',
                'fontSize': '11px',
                'display': 'inline-block',
                'marginTop': '3px'
            })
        ], style={
            'padding': '12px',  # Increased padding
            'borderBottom': '1px solid #eee',
            'borderLeft': f'3px solid {severity_color}'
        }))
    
    # Return header and alert items
    return [header] + alert_items

# Update the alert count badge
@app.callback(
    Output('alert-count-badge', 'children'),
    Input('app-interval-component', 'n_intervals')
)
def update_alert_badge(n):
    try:
        current_alert_count = count_alerts()
        return str(current_alert_count)
    except Exception as e:
        print(f"Error updating alert badge: {e}")
        # Return no_update to keep previous value
        return dash.no_update
        # OR use PreventUpdate to prevent update entirely
        # raise PreventUpdate

# Update the alert notification dot visibility (Now just ensures it stays visible)
@app.callback(
    Output('alert-notification-dot', 'style'),
    Input('app-interval-component', 'n_intervals'),
    State('alert-notification-dot', 'style') # Get the current style to preserve base properties
)
def update_alert_dot_visibility(n, current_style):
    # Ensure current_style is a dictionary (it should be from the layout)
    if current_style is None:
         # Define default style if None (should match layout)
         current_style = { 
            'position': 'absolute',
            'top': '2px', 
            'right': '-8px', 
            'width': '10px',
            'height': '10px',
            'backgroundColor': '#e74c3c', 
            'borderRadius': '50%',
            'display': 'block' # Default to block
        }

    updated_style = current_style.copy() # Work with a copy

    # Always ensure the dot is visible
    updated_style['display'] = 'block' 
            
    # Check if the style actually changed before returning
    if updated_style != current_style:
        return updated_style
    else:
        # Prevent unnecessary updates if the style is already correct
        raise PreventUpdate
        
    # Removed the try/except and count_alerts() as it's no longer needed for visibility logic
    # If you still need error handling for some reason, add it back.

# Keep the existing callback for toggling the alerts dropdown
@app.callback(
    Output("alerts-dropdown", "style"),
    Input("alerts-button", "n_clicks"),
    State("alerts-dropdown", "style"),
    prevent_initial_call=True
)
def toggle_alerts_dropdown(n_clicks, style):
    if n_clicks:
        current_style = style.copy()
        if current_style.get('display') == 'none':
            current_style['display'] = 'block'
            # Return the modified style to show dropdown
            return current_style
        else:
            current_style['display'] = 'none'
            # Return the modified style to hide dropdown
            return current_style
    return style

# Add a clientside callback to handle clicks outside the dropdown
clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        
        // Add the click listener if it doesn't exist
        if (!window.alertsClickOutsideListener) {
            window.alertsClickOutsideListener = function(event) {
                var dropdown = document.getElementById('alerts-dropdown');
                var button = document.getElementById('alerts-button');
                var container = document.getElementById('alerts-container');
                
                // Check if dropdown is visible and click is outside alerts-container
                if (dropdown && 
                    dropdown.style.display === 'block' && 
                    !container.contains(event.target)) {
                    
                    // Hide the dropdown
                    dropdown.style.display = 'none';
                }
            };
            
            // Add document-level click listener
            document.addEventListener('click', window.alertsClickOutsideListener);
        }
        
        return window.dash_clientside.no_update;
    }
    """,
    Output("click-outside-detector", "n_clicks", allow_duplicate=True),
    Input("alerts-dropdown", "style"),
    prevent_initial_call=True
)

# Add this callback to run window sensor checks periodically
@app.callback(
    Output("window-sensor-check-trigger", "children"),
    Input("app-interval-component", "n_intervals")
)
def check_window_sensors(n):
    # This is where you'd normally get real sensor data
    # For demonstration, we'll simulate some window sensors
    window_sensors = [
        {"id": "pi", "location": "Pi"}
    ]
    
    # Randomly simulate a window opening (for demo purposes)
    # In a real system, you would read actual sensor states
    if random.random() < 0.1:  # 10% chance on each interval
        sensor = random.choice(window_sensors)
        is_open = True
        print(f"Checking window sensor {sensor['id']} - Status: {'OPEN' if is_open else 'CLOSED'}")
        check_window_sensor(sensor["id"], is_open, sensor["location"])
    
    # Return empty div - we just need this output for the callback to work
    return ""

# Run the app
if __name__ == '__main__':
    # Seed the database with initial alerts if it's empty
    if influxdb_available():
        try:
            # Check if we already have alerts
            query = 'SELECT COUNT(*) FROM alerts'
            result = client.query(query)
            counts = list(result.get_points())
            alert_count = counts[0].get('count', 0) if counts else 0
            
            # If no alerts exist, add some initial ones
            if alert_count == 0:
                print("Seeding database with initial alerts...")
                initial_alerts = [
                    {"device": "Temperature Sensor 1", "message": "Temperature exceeds threshold", "severity": "high"},
                    {"device": "Humidity Sensor 3", "message": "Low battery warning", "severity": "medium"},
                    {"device": "Motion Sensor 2", "message": "Connection lost", "severity": "high"}
                ]
                for alert in initial_alerts:
                    add_alert(alert["device"], alert["message"], alert["severity"])
                print("Initial alerts added successfully")
        except Exception as e:
            print(f"Error seeding database with initial alerts: {e}")
    
    app.run(debug=False, host='0.0.0.0', port=8050)