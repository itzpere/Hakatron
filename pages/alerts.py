import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd

# Register this page in the app
dash.register_page(__name__, path='/alerts', title='Alerts')

# Sample alerts data (in a real app, this would come from a database)
sample_alerts = [
    {"id": 1, "device": "Temperature Sensor 1", "message": "Temperature exceeds threshold", "severity": "high", "time": "2023-10-15 14:32", "status": "active"},
    {"id": 2, "device": "Humidity Sensor 3", "message": "Low battery warning", "severity": "medium", "time": "2023-10-15 12:15", "status": "active"},
    {"id": 3, "device": "Motion Sensor 2", "message": "Connection lost", "severity": "high", "time": "2023-10-14 23:45", "status": "active"},
    {"id": 4, "device": "Temperature Sensor 5", "message": "Device offline", "severity": "low", "time": "2023-10-14 10:20", "status": "resolved"},
    {"id": 5, "device": "Gateway 1", "message": "CPU usage high", "severity": "medium", "time": "2023-10-13 17:45", "status": "active"},
    {"id": 6, "device": "Humidity Sensor 2", "message": "Humidity below threshold", "severity": "medium", "time": "2023-10-12 08:30", "status": "resolved"}
]

# Define severity colors and icons
severity_colors = {
    "high": "danger",     # Bootstrap danger color
    "medium": "warning",   # Bootstrap warning color
    "low": "info"         # Bootstrap info color
}

# Convert to DataFrame for easier filtering
df = pd.DataFrame(sample_alerts)

# Layout for the alerts page
layout = html.Div([
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
                        
                        # Action buttons with Bootstrap styling - Removed "Mark All as Read"
                        dbc.Col([
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
                            html.Th("Severity", className="table-header", style={'width': '10%'})
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

@callback(
    Output("alerts-table-body", "children"),
    [Input("severity-filter", "value")]  # Removed status-filter input
)
def update_alerts_table(severity):  # Removed status parameter
    # Filter the dataframe
    filtered_df = df.copy()
    
    if severity != 'all':
        filtered_df = filtered_df[filtered_df['severity'] == severity]
    
    # We no longer need to filter by status since we removed that UI element
    # But we'll keep showing all alerts regardless of status
    
    # Generate table rows with improved styling - Removed Status column
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
                    color=severity_colors[alert['severity']],
                    className="py-2 px-3"
                )
            )
        ]))
    
    # Show a message if no alerts match the filters - Adjusted colspan
    if not rows:
        rows = [html.Tr([
            html.Td(
                dbc.Alert(
                    "No alerts match the selected filters", 
                    color="light", 
                    className="text-center my-3"
                ),
                colSpan=4  # Changed from 5 to 4
            )
        ])]
    
    return rows
