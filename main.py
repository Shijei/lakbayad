"""
LakBayad v2.0 - Expense Splitting App
Main Entry Point - Modular Architecture
"""
import flet as ft
import config
from config import COLORS
from database import db
from auth import create_auth_view
from ui import (
    create_appbar,
    create_trip_selection_view,
    create_dashboard_layout,
    show_snackbar,
    show_error_dialog,
    ExpensesComponent,
    ParticipantsComponent,
    SettlementsComponent,
)


def main(page: ft.Page):
    """Main application entry point"""
    
    # Page configuration
    page.title = "LakBayad - Travel Expense Tracker"
    page.scroll = "adaptive"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = COLORS["bg"]
    page.padding = 0
    
    # Global state
    current_user_data = {
        'id': None,
        'display_name': '',
        'email': ''
    }
    
    all_participants = {}
    all_trips = {}
    
    # UI Components
    welcome_container = ft.Container()
    main_container = ft.Container(visible=False)
    
    # Initialize component instances
    expenses_component = ExpensesComponent()
    participants_component = ParticipantsComponent()
    settlements_component = SettlementsComponent()
    
    # Session management with version control
    SESSION_FILE = "session.json"
    APP_VERSION = "2.0.0"  # Increment this to force logout all users
    
    def save_session():
        """Save current session with app version"""
        import json
        try:
            with open(SESSION_FILE, "w") as f:
                json.dump({
                    'user_id': config.CURRENT_USER_ID,
                    'display_name': current_user_data['display_name'],
                    'email': current_user_data.get('email'),
                    'app_version': APP_VERSION  # Save version with session
                }, f)
        except:
            pass
    
    def load_session():
        """Load saved session (auto-logout if version changed)"""
        import json
        try:
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
                
                # Check app version - force logout if different
                saved_version = data.get('app_version', '1.0.0')
                if saved_version != APP_VERSION:
                    print(f"Version changed: {saved_version} → {APP_VERSION}. Forcing logout.")
                    clear_session()  # Clear old session
                    return False
                
                config.CURRENT_USER_ID = data.get('user_id')
                return True
        except:
            return False
    
    def clear_session():
        """Clear session file"""
        import os
        try:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
        except:
            pass
    
    def load_trips():
        """Load all user's trips"""
        try:
            response = db.get_user_trips(config.CURRENT_USER_ID)
            all_trips.clear()
            
            for row in response.data:
                trip = row['trips']
                if trip:
                    all_trips[trip['id']] = {
                        'name': trip['name'],
                        'is_active': trip.get('is_active', True),
                        'invite_code': trip['invite_code'],
                        'created_by': trip.get('created_by')
                    }
        except Exception as ex:
            print(f"Load trips error: {ex}")
    
    def logout_user(e=None):
        """Logout and return to auth screen"""
        config.CURRENT_USER_ID = None
        config.CURRENT_TRIP_ID = None
        current_user_data.clear()
        all_participants.clear()
        all_trips.clear()
        clear_session()
        
        page.appbar = None
        welcome_container.visible = True
        main_container.visible = False
        page.update()
        
        show_snackbar(page, "Logged out")
    
    def update_appbar():
        """Update appbar with current state"""
        if config.CURRENT_USER_ID:
            create_appbar(page, current_user_data, logout_user, update_appbar)
    
    def on_auth_success(user):
        """Called after successful authentication"""
        current_user_data['id'] = user['id']
        current_user_data['display_name'] = user['display_name']
        current_user_data['email'] = user.get('email')
        
        config.CURRENT_USER_ID = user['id']
        save_session()
        load_trips()
        
        # Always show trip selection first (no auto-select)
        config.CURRENT_TRIP_ID = None
        all_participants.clear()
        show_trip_selection()
        
        update_appbar()
        welcome_container.visible = False
        main_container.visible = True
        page.update()
    
    def show_trip_selection():
        """Show trip selection screen"""
        trip_selection_view = create_trip_selection_view(
            page,
            all_trips,
            all_participants,
            on_trip_selected,
            lambda msg: show_snackbar(page, msg),
            lambda title, msg: show_error_dialog(page, title, msg)
        )
        
        main_container.content = trip_selection_view
        page.update()
    
    def on_trip_selected(trip_id: str, trip_name: str):
        """Called when user selects a trip"""
        config.CURRENT_TRIP_ID = trip_id
        config.CURRENT_TRIP_CREATOR = all_trips[trip_id].get('created_by')
        
        show_snackbar(page, f"📍 {trip_name}")
        show_dashboard()
    
    # Declare refresh_dashboard as None initially
    refresh_dashboard = None
    
    def show_dashboard():
        """Show main dashboard"""
        nonlocal refresh_dashboard
        
        # Create offline indicator
        from ui.offline_indicator import create_offline_indicator
        offline_indicator = create_offline_indicator(page, db)
        
        # Create dashboard layout
        dashboard_container, refresh_function = create_dashboard_layout(
            page,
            all_participants,
            all_trips,
            show_trip_selection,
            expenses_component,
            participants_component,
            settlements_component
        )
        
        # Add offline indicator to top of dashboard
        dashboard_with_indicator = ft.Column([
            offline_indicator,
            dashboard_container
        ], spacing=0)
        
        # Store refresh function
        refresh_dashboard = refresh_function
        
        # Set page reference for components
        settlements_component.set_page_and_callback(page, refresh_dashboard)
        
        main_container.content = dashboard_with_indicator  # Use wrapped version
        page.update()
        
        # Initial data load
        refresh_dashboard(None)
    
    # Initialize auth view
    # Note: create_auth_view takes (page, callback)
    # The callback receives user data on successful auth
    auth_view = create_auth_view(page, on_auth_success)
    
    welcome_container.content = auth_view
    
    # Check for existing session
    if load_session() and config.CURRENT_USER_ID:
        try:
            # Try to get user from database (online)
            user_result = db.get_user_by_id(config.CURRENT_USER_ID)
            if user_result.data:
                # Clear trip selection on auto-login
                config.CURRENT_TRIP_ID = None
                on_auth_success(user_result.data[0])
        except Exception as e:
            # If offline or error, use cached session data
            print(f"[DEBUG] Online user fetch failed: {e}")
            print(f"[DEBUG] Using cached session for offline mode")
            
            # Load user data from session file
            import json
            try:
                with open(SESSION_FILE, "r") as f:
                    session_data = json.load(f)
                    
                # Create user object from session
                user = {
                    'id': session_data.get('user_id'),
                    'display_name': session_data.get('display_name'),
                    'email': session_data.get('email')
                }
                
                # Set current user
                current_user_data['id'] = user['id']
                current_user_data['display_name'] = user['display_name']
                current_user_data['email'] = user.get('email')
                config.CURRENT_USER_ID = user['id']
                
                # Clear trip selection
                config.CURRENT_TRIP_ID = None
                
                # Load cached trips (offline mode)
                load_trips()
                
                # Show trip selection
                show_trip_selection()
                
                update_appbar()
                welcome_container.visible = False
                main_container.visible = True
                page.update()
                
                print(f"[DEBUG] Offline mode: Loaded session for {user['display_name']}")
            except Exception as session_err:
                print(f"[DEBUG] Failed to load session: {session_err}")
                pass
    
    # Add to page
    page.add(welcome_container, main_container)


if __name__ == "__main__":
    print("✓ Database connected")
    ft.app(
        main,
        view=ft.AppView.WEB_BROWSER,
        port=getattr(config, 'APP_PORT', 8000),  # Use config.APP_PORT or default 8000
        assets_dir="assets"
    )