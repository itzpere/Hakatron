import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
from influxdb import InfluxDBClient
import datetime
import json

# Register this page in the app
dash.register_page(__name__, path='/alerts', title='Alerts')

# InfluxDB Connection Parameters
INFLUXDB_URL = "10.147.18.192"
INFLUXDB_PORT = 8086
INFLUXDB_USER = "admin"
INFLUXDB_PASSWORD = "mia"
INFLUXDB_DATABASE = "mydb"

# Define severity colors and icons
severity_colors = {
    "high": "danger",     # Bootstrap danger color
    "medium": "warning",   # Bootstrap warning color
    "low": "info"         # Bootstrap info color
}

# Function to connect to InfluxDB
def get_influxdb_client():
    try:
        client = InfluxDBClient(
            host=INFLUXDB_URL,
            port=INFLUXDB_PORT,
            username=INFLUXDB_USER,
            password=INFLUXDB_PASSWORD
        )
        # Create database if it doesn't exist
        if INFLUXDB_DATABASE not in [db['name'] for db in client.get_list_database()]:
            client.create_database(INFLUXDB_DATABASE)
        client.switch_database(INFLUXDB_DATABASE)
        return client
    except Exception as e:
        print(f"Error connecting to InfluxDB: {e}")
        return None

# Function to get alerts from InfluxDB
def get_alerts_from_db(severity_filter='all'):
    """
    Retrieve alerts from InfluxDB with optional filtering
    """
    # Sample alerts as fallback data if DB connection fails
    sample_alerts = [
        {"id": 1, "device": "Temperature Sensor 1", "message": "Temperature exceeds threshold", "severity": "high", "time": "2023-10-15 14:32", "status": "active"},
        {"id": 2, "device": "Humidity Sensor 3", "message": "Low battery warning", "severity": "medium", "time": "2023-10-15 12:15", "status": "active"},
        {"id": 3, "device": "Motion Sensor 2", "message": "Connection lost", "severity": "high", "time": "2023-10-14 23:45", "status": "active"},
        {"id": 4, "device": "Temperature Sensor 5", "message": "Device offline", "severity": "low", "time": "2023-10-14 10:20", "status": "resolved"},
        {"id": 5, "device": "Gateway 1", "message": "CPU usage high", "severity": "medium", "time": "2023-10-13 17:45", "status": "active"},
        {"id": 6, "device": "Humidity Sensor 2", "message": "Humidity below threshold", "severity": "medium", "time": "2023-10-12 08:30", "status": "resolved"}
    ]
    
    try:
        client = get_influxdb_client()
        if not client:
            return pd.DataFrame(sample_alerts)
        
        # Build the query based on filters
        if severity_filter != 'all':
            query = f'SELECT * FROM alerts WHERE severity = \'{severity_filter}\' ORDER BY time DESC'
        else:
            query = 'SELECT * FROM alerts ORDER BY time DESC'

        # Execute query
        result = client.query(query)
        
        if not result:
            # Return sample data if no results
            return pd.DataFrame(sample_alerts)
        
        # Process results
        alerts = []
        for point in result.get_points(measurement='alerts'):
            # Format the timestamp - convert from InfluxDB ISO format to user-friendly string
            time_str = point.get('time', '')
            if time_str:
                # Parse ISO format and convert to readable format
                try:
                    dt = datetime.datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    formatted_time = time_str
            else:
                formatted_time = "Unknown"
                
            alert = {
                "id": point.get('alert_id', len(alerts) + 1),
                "device": point.get('device', 'Unknown Device'),
                "message": point.get('message', 'No message'),
                "severity": point.get('severity', 'medium'),
                "time": formatted_time,
                "status": point.get('status', 'active')
            }
            alerts.append(alert)
            
        # If no alerts found in database, use sample data
        if not alerts:
            # Create initial alerts in database (only if we're not filtering)
            if severity_filter == 'all':
                for alert in sample_alerts:
                    json_body = [
                        {
                            "measurement": "alerts",
                            "tags": {
                                "device": alert["device"],
                                "severity": alert["severity"]
                            },
                            "fields": {
                                "alert_id": alert["id"],
                                "message": alert["message"],
                                "device": alert["device"],
                                "severity": alert["severity"],
                                "status": alert["status"]
                            }
                        }
                    ]
                    client.write_points(json_body)
                
                # Try query again
                result = client.query('SELECT * FROM alerts ORDER BY time DESC')
                for point in result.get_points(measurement='alerts'):
                    time_str = point.get('time', '')
                    if time_str:
                        try:
                            dt = datetime.datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                            formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            formatted_time = time_str
                    else:
                        formatted_time = "Unknown"
                        
                    alert = {
                        "id": point.get('alert_id', len(alerts) + 1),
                        "device": point.get('device', 'Unknown Device'),
                        "message": point.get('message', 'No message'),
                        "severity": point.get('severity', 'medium'),
                        "time": formatted_time,
                        "status": point.get('status', 'active')
                    }
                    alerts.append(alert)
            
            # If still no alerts, use sample data
            if not alerts:
                return pd.DataFrame(sample_alerts)
                
        return pd.DataFrame(alerts)
        
    except Exception as e:
        print(f"Error retrieving alerts from InfluxDB: {e}")
        return pd.DataFrame(sample_alerts)

# Function to add a new alert to InfluxDB
def add_alert_to_db(device, message, severity="medium", status="active"):
    """
    Add a new alert to InfluxDB
    """
    try:
        client = get_influxdb_client()
        if not client:
            return False
        
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
                    "severity": severity,
                    "status": status
                }
            }
        ]
        
        # Write to InfluxDB
        success = client.write_points(json_body)
        return success
    except Exception as e:
        print(f"Error adding alert to InfluxDB: {e}")
        return False

# Function to test the database connection
def test_db_connection():
    client = get_influxdb_client()
    if client:
        try:
            client.ping()
            return True
        except:
            return False
    return False

# Add interval component for refreshing data
layout = html.Div([
    # Add interval component for refreshing
    dcc.Interval(
        id='alerts-refresh-interval',
        interval=10*1000,  # Refresh every 10 seconds
        n_intervals=0
    ),
    
    # Database connection status indicator
    dbc.Alert(
        id="db-connection-alert",
        color="info",
        dismissable=True,
        is_open=False
    ),
    
    # Header with better styling
    dbc.Row([
        dbc.Col(html.H2("System Alerts", className="mb-3"), width=12),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        # Filter controls with better layout - Keep only severity filter
                        dbc.Col([
                            html.Label("Filter by severity:", className="me-2"),
                            dbc.Select(
                                id='severity-filter',
                                options=[
                                    {'label': 'All Severities', 'value': 'all'},
                                    {'label': 'High', 'value': 'high'},
                                    {'label': 'Medium', 'value': 'medium'},
                                    {'label': 'Low', 'value': 'low'}
                                ],
                                value='all',
                                style={'maxWidth': '200px'}
                            ),
                        ], width=12, md=6, className="mb-3 mb-md-0"),
                        
                        # Add test alert button and export button
                        dbc.Col([
                            dbc.Button(
                                "Add Test Alert",
                                id="add-test-alert-btn",
                                color="primary",
                                className="me-2"
                            ),
                            dbc.Button(
                                "Export", 
                                id="export-alerts-btn", 
                                color="outline-secondary"
                            )
                        ], width=12, md=6, className="text-md-end")
                    ])
                ])
            ], className="mb-4")
        ], width=12)
    ]),
    
    # Alerts table with Bootstrap styling - Removed Status column
    dbc.Row([
        dbc.Col([
            html.Div(id="alerts-table-container", children=[
                dbc.Table([
                    # Table header - Adjusted column widths
                    html.Thead(
                        html.Tr([
                            html.Th("Time", className="table-header", style={'width': '15%'}),
                            html.Th("Device", className="table-header", style={'width': '25%'}),
                            html.Th("Message", className="table-header", style={'width': '50%'}),
                            html.Th("Severity", className="table-header", style={'width': '10%'}),
                        ], className="table-light")
                    ),
                    
                    # Table body - will be populated by callback
                    html.Tbody(id="alerts-table-body")
                ], bordered=True, hover=True, responsive=True, striped=True)
            ])
        ], width=12)
    ]),
    
    # Pagination with Bootstrap styling
    dbc.Row([
        dbc.Col([
            dbc.Pagination(
                id="alerts-pagination",
                max_value=1,
                first_last=True,
                previous_next=True,
                active_page=1,
                className="justify-content-center mt-4"
            )
        ], width=12, className="text-center")
    ])
])

# Update the callback to use database data
@callback(
    Output("alerts-table-body", "children"),
    [Input("severity-filter", "value"),
     Input("alerts-refresh-interval", "n_intervals"),
     Input("add-test-alert-btn", "n_clicks")]
)
def update_alerts_table(severity, n_intervals, n_clicks):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
    
    # Add test alert if button was clicked
    if triggered_id == "add-test-alert-btn" and n_clicks:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        device = f"Test Device {n_clicks}"
        message = f"Test alert created at {current_time}"
        severity_val = ["low", "medium", "high"][n_clicks % 3]
        add_alert_to_db(device, message, severity_val)
    
    # Get filtered alerts from database
    filtered_df = get_alerts_from_db(severity)
    
    # Generate table rows with improved styling
    rows = []
    for _, alert in filtered_df.iterrows():
        # Create row with better formatting
        rows.append(html.Tr([
            html.Td(alert['time']),
            html.Td(html.Strong(alert['device'])),
            html.Td(alert['message']),
            html.Td(
                dbc.Badge(
                    alert['severity'].capitalize(),
                    color=severity_colors.get(alert['severity'], "secondary"),
                    className="py-2 px-3"
                )
            )
        ]))
    
    # Show a message if no alerts match the filters
    if not rows:
        rows = [html.Tr([
            html.Td(
                dbc.Alert(
                    "No alerts match the selected filters", 
                    color="light", 
                    className="text-center my-3"
                ),
                colSpan=4
            )
        ])]
    
    return rows

# Callback to show DB connection status
@callback(
    [Output("db-connection-alert", "children"),
     Output("db-connection-alert", "color"),
     Output("db-connection-alert", "is_open")],
    Input("alerts-refresh-interval", "n_intervals")
)
def update_db_status(n):
    connection_ok = test_db_connection()
    if connection_ok:
        return "Connected to InfluxDB successfully.", "success", True
    else:
        return "Could not connect to InfluxDB. Using sample data.", "warning", True
