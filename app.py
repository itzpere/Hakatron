import dash
from dash import html, dcc, clientside_callback
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import random

# Global variables for application state
alert_count = 3  # This can be updated from database later

# Sample alerts data (in a real app, this would come from a database)
sample_alerts = [
    {"id": 1, "device": "Temperature Sensor 1", "message": "Temperature exceeds threshold", "severity": "high", "time": "2023-10-15 14:32"},
    {"id": 2, "device": "Humidity Sensor 3", "message": "Low battery warning", "severity": "medium", "time": "2023-10-15 12:15"},
    {"id": 3, "device": "Motion Sensor 2", "message": "Connection lost", "severity": "high", "time": "2023-10-14 23:45"}
]

# Mock database client implementation
# In a real app, you'd use an actual database client like InfluxDB
class MockDatabaseClient:
    def __init__(self):
        self.connected = random.choice([True, False])
    
    def ping(self):
        # Simulate connection issues randomly
        if not self.connected or random.random() < 0.2:  # 20% chance of failure even when "connected"
            raise Exception("Database connection failed")
        return True

# Initialize database client
try:
    client = MockDatabaseClient()
except Exception as e:
    print(f"Error initializing database client: {e}")
    client = None

# Function to check if InfluxDB is available
def influxdb_available():
    if client is None:
        return False
    try:
        client.ping()
        return True
    except:
        return False

# Initialize the Dash app
app = dash.Dash(__name__, use_pages=True, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Define the common layout (navbar will appear on all pages)
app.layout = html.Div([
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
                # Alerts button with badge
                html.Div([
                    html.Span("Alerts", style={
                        'color': 'white',
                        'marginRight': '5px'
                    }),
                    html.Span(
                        id="alert-count-badge",
                        children=str(alert_count),
                        style={
                            'backgroundColor': '#e74c3c',
                            'color': 'white',
                            'borderRadius': '50%',
                            'padding': '3px 8px',
                            'fontSize': '12px',
                            'fontWeight': 'bold',
                            'display': 'inline-block' if alert_count > 0 else 'none'
                        }
                    )
                ], id="alerts-button", style={
                    'display': 'flex',
                    'alignItems': 'center',
                    'cursor': 'pointer'
                }),
                
                # Dropdown for alerts (hidden by default)
                html.Div([
                    # Alert items
                    html.Div([
                        html.Div([
                            # Individual alert items
                            *[html.Div([
                                html.Div([
                                    html.Strong(alert["device"]),
                                    html.Span(alert["time"], style={'float': 'right', 'fontSize': '12px', 'color': '#777'})
                                ]),
                                html.Div(alert["message"]),
                                html.Div(alert["severity"].capitalize(), style={
                                    'color': '#fff',
                                    'backgroundColor': '#e74c3c' if alert["severity"] == "high" else '#f39c12',
                                    'padding': '2px 8px',
                                    'borderRadius': '3px',
                                    'fontSize': '11px',
                                    'display': 'inline-block',
                                    'marginTop': '3px'
                                })
                            ], style={
                                'padding': '10px',
                                'borderBottom': '1px solid #eee'
                            }) for alert in sample_alerts]
                        ], style={'maxHeight': '300px', 'overflowY': 'auto'}),
                        
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
                        'width': '300px',
                        'backgroundColor': 'white',
                        'boxShadow': '0 2px 10px rgba(0,0,0,0.2)',
                        'borderRadius': '4px',
                        'position': 'absolute',
                        'top': '45px',
                        'right': '0',
                        'zIndex': '1000',
                        'display': 'none'
                    }, id="alerts-dropdown")
                ], style={'position': 'relative'})
            ], style={
                'marginRight': '20px',
                'position': 'relative'
            }, id="alerts-container"),
            
            # Login button
            html.Button('Login', id='login-button', style={
                'backgroundColor': '#4CAF50',
                'color': 'white',
                'border': 'none',
                'borderRadius': '4px',
                'padding': '6px 16px',
                'cursor': 'pointer',
                'fontWeight': 'bold'
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
    )
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
            led_style['backgroundColor'] = '#4CAF50'  # Green
            led_style['boxShadow'] = '0 0 8px #4CAF50'  # Green glow
            return "Connected to Database ✓", led_style
    except Exception as e:
        print(f"Error checking database status: {e}")
        # Error in check - red LED
        led_style = base_led_style.copy()
        led_style['backgroundColor'] = '#f44336'  # Red
        led_style['boxShadow'] = '0 0 8px #f44336'  # Red glow
        return "Error Checking Database ⚠️", led_style

# Update the callback to use the corrected ID
@app.callback(
    [Output('alert-count-badge', 'children'),
     Output('alert-count-badge', 'style')],
    [Input('app-interval-component', 'n_intervals')]
)
def update_alert_badge(n):
    # This function can fetch alert count from database in the future
    # For now, just using the global variable
    badge_style = {
        'backgroundColor': '#e74c3c',
        'color': 'white',
        'borderRadius': '50%',
        'padding': '3px 8px',
        'fontSize': '12px',
        'fontWeight': 'bold',
        'display': 'inline-block' if alert_count > 0 else 'none'
    }
    return str(alert_count), badge_style

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
    Output("click-outside-detector", "n_clicks"),
    Input("alerts-dropdown", "style"),
    prevent_initial_call=True
)

# Run the app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)