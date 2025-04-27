import dash
from dash import html, dcc, callback, Input, Output, State, ALL
import dash_bootstrap_components as dbc
from influxdb import InfluxDBClient
import datetime
import json

# Register the page
dash.register_page(__name__, path='/profile', title='User Profile', name='Profile')

# InfluxDB Connection Parameters (same as in app.py)
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
    client.switch_database(INFLUXDB_DATABASE)
    print("Profile page connected to InfluxDB")
except Exception as e:
    print(f"Error initializing InfluxDB client in profile: {e}")
    client = None

# Sample user data - In a real app, this would come from a database
# For demo purposes, we'll use this directly
USERS = [
    {"id": "user1", "username": "admin", "email": "admin@example.com", "role": "admin", 
     "access": ["temperature", "humidity", "motion", "window", "light"]},
    {"id": "user2", "username": "john", "email": "john@example.com", "role": "user", 
     "access": ["temperature", "humidity"]},
    {"id": "user3", "username": "alice", "email": "alice@example.com", "role": "user", 
     "access": ["temperature", "window"]},
    {"id": "user4", "username": "bob", "email": "bob@example.com", "role": "user", 
     "access": ["motion", "light"]}
]

# Available sensor types with icons
SENSOR_TYPES = [
    {"value": "temperature", "label": "🌡️ Temperature Sensors", "description": "Access to temperature readings and controls"},
    {"value": "humidity", "label": "💧 Humidity Sensors", "description": "Access to humidity readings and controls"},
    {"value": "motion", "label": "👁️ Motion Sensors", "description": "Access to motion detection sensors"},
    {"value": "window", "label": "🪟 Window Sensors", "description": "Access to window state sensors"},
    {"value": "light", "label": "💡 Light Controls", "description": "Access to light switches and dimmers"}
]

# Function to get current user - in a real app this would check auth status
def get_current_user():
    # For demo, default to the admin user
    return USERS[0]

# Function to save user changes to database
def save_user(user):
    if client is None:
        print("Cannot save user: No database connection")
        return False
    
    try:
        # Create a data point
        json_body = [
            {
                "measurement": "users",
                "tags": {
                    "user_id": user["id"],
                    "role": user["role"]
                },
                "fields": {
                    "username": user["username"],
                    "email": user["email"],
                    "access": json.dumps(user["access"]),
                    "role": user["role"]
                }
            }
        ]
        
        # Write to InfluxDB
        success = client.write_points(json_body)
        return success
    except Exception as e:
        print(f"Error saving user: {e}")
        return False

# User profile component
def render_user_profile(user):
    return dbc.Card([
        dbc.CardHeader([
            html.H4("My Profile", className="card-title"),
            html.P("Manage your account settings and preferences", className="card-text text-muted")
        ]),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Img(src="/assets/default-avatar.png", alt="Profile avatar", 
                             style={"width": "120px", "height": "120px", "borderRadius": "50%", "objectFit": "cover"})
                ], width=3, className="text-center"),
                dbc.Col([
                    dbc.Form([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Username"),
                                dbc.Input(type="text", value=user["username"], disabled=True),
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Email"),
                                dbc.Input(type="email", value=user["email"], id="user-email"),
                            ], width=6),
                        ], className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Role"),
                                dbc.Input(type="text", value=user["role"].capitalize(), disabled=True),
                            ], width=6),
                            dbc.Col([
                                dbc.Button("Update Profile", color="primary", id="update-profile-btn"),
                            ], width=6, className="d-flex align-items-end"),
                        ]),
                    ])
                ], width=9),
            ]),
            html.Hr(),
            
            # Improved Sensor Access Section with header and stats
            html.Div([
                # Header with access statistics
                dbc.Row([
                    dbc.Col([
                        html.H5("Your Sensor Access", className="mb-0"),
                    ], width="auto"),
                    dbc.Col([
                        html.Span(f"{len([s for s in SENSOR_TYPES if s['value'] in user['access']])}/{len(SENSOR_TYPES)} sensors accessible", 
                                 className="badge bg-primary")
                    ], width="auto", className="ms-auto")
                ], className="mb-3 d-flex align-items-center"),
                
                # Access cards with search and filter options
                dbc.Row([
                    dbc.Col([
                        dbc.Input(placeholder="Search sensors...", type="text", id="sensor-search", className="mb-3")
                    ], width=12)
                ]),
                
                # Filter tabs for all/granted/not granted
                dbc.Tabs([
                    dbc.Tab([
                        dbc.Row([
                            render_sensor_access_card(sensor_type, sensor_type["value"] in user["access"], False)
                            for sensor_type in SENSOR_TYPES
                        ], className="mt-3")
                    ], label="All Sensors", tab_id="all-sensors"),
                    dbc.Tab([
                        dbc.Row([
                            render_sensor_access_card(sensor_type, True, False)
                            for sensor_type in SENSOR_TYPES if sensor_type["value"] in user["access"]
                        ], className="mt-3") if any(sensor_type["value"] in user["access"] for sensor_type in SENSOR_TYPES) else
                        html.Div("You don't have access to any sensors yet.", className="text-muted text-center py-4")
                    ], label="Granted Access", tab_id="granted-access"),
                    dbc.Tab([
                        dbc.Row([
                            render_sensor_access_card(sensor_type, False, False)
                            for sensor_type in SENSOR_TYPES if sensor_type["value"] not in user["access"]
                        ], className="mt-3") if any(sensor_type["value"] not in user["access"] for sensor_type in SENSOR_TYPES) else
                        html.Div("You have access to all sensors!", className="text-success text-center py-4")
                    ], label="No Access", tab_id="no-access"),
                ], id="sensor-access-tabs", active_tab="all-sensors"),
                
                # Help text at bottom
                html.P([
                    html.I(className="fas fa-info-circle me-2 text-info"),
                    "Contact your administrator if you need additional sensor access."
                ], className="text-muted small mt-3")
            ], className="sensor-access-container mt-4")
        ])
    ], className="mb-4")

# Admin user management component
def render_admin_panel():
    return dbc.Card([
        dbc.CardHeader([
            html.H4("User Management", className="card-title"),
            html.P("Manage users and their access permissions", className="card-text text-muted")
        ]),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Button([
                        html.I(className="fas fa-plus-circle me-2"),
                        "Create New User"
                    ], color="success", className="mb-3", id="create-user-btn")
                ], width=12),
            ]),
            html.Div([
                render_user_card(user)
                for user in USERS
            ], id="user-cards-container")
        ])
    ])

# Sensor access card component
def render_sensor_access_card(sensor_type, has_access, is_admin_view=False, user_id=None):
    # Larger, more detailed icons for each sensor type
    icons = {
        "temperature": "fas fa-temperature-high fa-2x",
        "humidity": "fas fa-tint fa-2x",
        "motion": "fas fa-running fa-2x",
        "window": "fas fa-window-maximize fa-2x",
        "light": "fas fa-lightbulb fa-2x"
    }
    
    icon_class = icons.get(sensor_type["value"], "fas fa-microchip fa-2x")
    card_color = "success" if has_access else "light"
    text_color = "white" if has_access else "dark"
    
    # Status badge
    status_badge = html.Span(
        "Granted" if has_access else "No Access",
        className=f"badge bg-{'success' if has_access else 'secondary'} position-absolute",
        style={"top": "10px", "right": "10px"}
    )
    
    # Create a more informative card with usage details and last access
    card = dbc.Card([
        dbc.CardBody([
            html.Div([
                # Icon column
                html.Div([
                    html.I(className=icon_class, style={
                        "color": "#fff" if has_access else "#6c757d",
                        "backgroundColor": "#28a745" if has_access else "#f8f9fa", 
                        "padding": "15px",
                        "borderRadius": "50%",
                        "width": "60px",
                        "height": "60px",
                        "display": "flex",
                        "alignItems": "center",
                        "justifyContent": "center"
                    })
                ], style={"marginRight": "15px"}),
                
                # Content column
                html.Div([
                    html.H5(sensor_type["label"].replace('🌡️', '').replace('💧', '').replace('👁️', '').replace('🪟', '').replace('💡', ''), 
                           className=f"text-{text_color} mb-1"),
                    html.P(sensor_type["description"], 
                          className=f"text-{text_color if has_access else 'muted'} small mb-2"),
                    
                    # Additional details for granted access
                    html.Div([
                        html.Small([
                            html.I(className="fas fa-check-circle text-success me-1"),
                            "Full access granted"
                        ], className="d-block mb-1"),
                        html.Small([
                            html.I(className="fas fa-clock text-info me-1"),
                            "Last accessed: Today, 10:45 AM"
                        ], className="d-block text-muted")
                    ]) if has_access else html.Div([
                        html.Small([
                            html.I(className="fas fa-lock text-secondary me-1"),
                            "Contact administrator for access"
                        ], className="d-block text-muted")
                    ])
                ], style={"flex": "1"})
            ], style={"display": "flex", "alignItems": "center"}),
            
            # Admin controls at the bottom if in admin view
            html.Div([
                html.Hr(className="my-2"),
                dbc.Switch(
                    id={"type": "sensor-access-switch", "user_id": user_id, "sensor": sensor_type["value"]},
                    value=has_access,
                    label="Toggle Access Rights",
                    className="mt-2"
                )
            ]) if is_admin_view else None,
            
            # Status badge
            status_badge
        ], className="p-3 position-relative")
    ], color=card_color, className="mb-3 sensor-card", style={
        "borderLeft": f"5px solid {'#28a745' if has_access else '#f8f9fa'}",
        "transition": "transform 0.2s",
        "cursor": "pointer"
    })
    
    if is_admin_view:
        return dbc.Col(card, width=12, sm=6, className="mb-3")
    else:
        return dbc.Col(card, width=12, sm=6, md=4, className="mb-3")

# User card component for admin panel
def render_user_card(user):
    return dbc.Card([
        dbc.CardHeader([
            dbc.Row([
                dbc.Col(html.H5(user["username"], className="mb-0"), width="auto"),
                dbc.Col(
                    html.Span(user["role"].upper(), className=f"badge bg-{'primary' if user['role'] == 'admin' else 'secondary'}"),
                    width="auto", className="ms-auto"
                )
            ])
        ]),
        dbc.CardBody([
            html.P(f"Email: {user['email']}"),
            html.P([
                html.Strong("Access: "),
                ", ".join(access.capitalize() for access in user["access"]) if user["access"] else "No access"
            ]),
            dbc.ButtonGroup([
                dbc.Button("Edit", color="primary", size="sm", id={"type": "edit-user-btn", "index": user["id"]}),
                dbc.Button("Delete", color="danger", size="sm", id={"type": "delete-user-btn", "index": user["id"]}),
                dbc.Button(
                    "Remove Admin" if user["role"] == "admin" else "Make Admin", 
                    color="warning", size="sm",
                    id={"type": "toggle-admin-btn", "index": user["id"]}
                )
            ], className="mt-2")
        ])
    ], className="mb-3")

# Function to create edit user modal
def create_edit_user_modal(user):
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(f"Edit User: {user['username']}")),
        dbc.ModalBody([
            dbc.Form([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Username"),
                        dbc.Input(type="text", value=user["username"], id="edit-username")
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Email"),
                        dbc.Input(type="email", value=user["email"], id="edit-email")
                    ], width=6)
                ], className="mb-3"),
                html.H5("Sensor Access", className="mt-4 mb-3"),
                dbc.Row([
                    render_sensor_access_card(
                        sensor_type, 
                        sensor_type["value"] in user["access"], 
                        is_admin_view=True,
                        user_id=user["id"]
                    )
                    for sensor_type in SENSOR_TYPES
                ])
            ])
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="edit-user-cancel", className="me-2", color="secondary"),
            dbc.Button("Save Changes", id="edit-user-save", color="primary")
        ])
    ], id="edit-user-modal", size="lg")

# Main layout with tabs for different sections
layout = html.Div([
    dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.H1("User Profile", className="mb-4"),
                html.P("Manage your account and access permissions", className="lead text-muted")
            ], width=12)
        ], className="mb-4"),
        
        # Current user profile
        html.Div(id="profile-content"),
        
        # Edit user modal placeholder
        html.Div(id="modal-container"),
        
        # Status message area
        dbc.Alert(id="status-message", is_open=False, duration=4000, dismissable=True)
    ], className="py-4")
])

# Callback to load profile content based on user role
@callback(
    Output("profile-content", "children"),
    Input("profile-content", "id")  # Just to trigger the callback on page load
)
def load_profile_content(_):
    current_user = get_current_user()
    
    if current_user["role"] == "admin":
        # Show both user profile and admin panel
        return [
            # User's own profile
            render_user_profile(current_user),
            # Admin panel for user management
            render_admin_panel()
        ]
    else:
        # Regular user only sees their profile
        return render_user_profile(current_user)

# Callback to handle showing edit user modal
@callback(
    Output("modal-container", "children"),
    Input({"type": "edit-user-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def show_edit_modal(n_clicks):
    if not any(n_clicks) or all(n is None for n in n_clicks):
        return None
    
    # Find which button was clicked
    ctx = dash.callback_context
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    user_id = json.loads(button_id)["index"]
    
    # Find the user
    user = next((u for u in USERS if u["id"] == user_id), None)
    if user:
        return create_edit_user_modal(user)
    return None

# Callback to close edit modal
@callback(
    Output("edit-user-modal", "is_open", allow_duplicate=True),
    [Input("edit-user-cancel", "n_clicks"), 
     Input("edit-user-save", "n_clicks")],
    State("edit-user-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_modal(cancel_clicks, save_clicks, is_open):
    if cancel_clicks or save_clicks:
        return not is_open
    return is_open

# Callback to update user profile
@callback(
    Output("status-message", "children"),
    Output("status-message", "is_open"),
    Output("status-message", "color"),
    Input("update-profile-btn", "n_clicks"),
    State("user-email", "value"),
    prevent_initial_call=True
)
def update_profile(n_clicks, email):
    if not n_clicks:
        return "", False, "success"
    
    # Update the current user's email
    current_user = get_current_user()
    current_user["email"] = email
    
    # Save changes
    success = save_user(current_user)
    
    if success:
        return "Profile updated successfully!", True, "success"
    else:
        return "Failed to update profile. Please try again.", True, "danger"

# Callback to handle toggling admin status
@callback(
    Output("user-cards-container", "children"),
    Input({"type": "toggle-admin-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def toggle_admin_status(n_clicks):
    if not any(n_clicks) or all(n is None for n in n_clicks):
        return [render_user_card(user) for user in USERS]
    
    # Find which button was clicked
    ctx = dash.callback_context
    if not ctx.triggered:
        return [render_user_card(user) for user in USERS]
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    user_id = json.loads(button_id)["index"]
    
    # Toggle the role of the user
    for user in USERS:
        if user["id"] == user_id:
            user["role"] = "user" if user["role"] == "admin" else "admin"
            # Try to save changes
            save_user(user)
            break
    
    # Return updated cards
    return [render_user_card(user) for user in USERS]

# Add database initialization code
def init_users_database():
    if client is None:
        print("Cannot initialize users database: No connection")
        return
    
    try:
        # Check if users measurement exists
        result = client.query("SHOW MEASUREMENTS")
        measurements = list(result.get_points())
        has_users = any(m.get('name') == 'users' for m in measurements)
        
        if not has_users:
            print("Initializing users database...")
            # Add sample users to database
            for user in USERS:
                save_user(user)
            print("Users database initialized successfully")
    except Exception as e:
        print(f"Error initializing users database: {e}")

# Initialize users when module loads
init_users_database()