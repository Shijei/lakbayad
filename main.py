"""
LakBayad ₱ - Trip Expense Splitter
Main application file
"""
import flet as ft
import config
from config import COLORS
from database import db
from utils import *
from auth import create_auth_view
from expenses import create_expenses_view
from participants import create_participants_view
from dashboard import create_dashboard_view


def main(page: ft.Page):
    page.title = config.APP_TITLE
    page.scroll = "adaptive"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = COLORS["bg"]
    page.padding = 0
    
    # Data structures
    all_participants = {}
    all_trips = {}
    current_user_data = {}
    
    # ==================== HELPERS ====================
    
    def save_session():
        """Save session to client storage"""
        try:
            page.client_storage.set("current_user_id", config.CURRENT_USER_ID)
            page.client_storage.set("current_trip_id", config.CURRENT_TRIP_ID)
        except:
            pass
    
    def load_session():
        """Load session from client storage"""
        try:
            config.CURRENT_USER_ID = page.client_storage.get("current_user_id")
            config.CURRENT_TRIP_ID = page.client_storage.get("current_trip_id")
            return config.CURRENT_USER_ID is not None
        except:
            return False
    
    def show_snackbar(message: str, error: bool = False):
        """Show snackbar"""
        page.snack_bar = ft.SnackBar(
            ft.Text(message, color=COLORS["surface"], size=14),
            bgcolor=COLORS["error"] if error else COLORS["success"],
            duration=3000
        )
        page.snack_bar.open = True
        page.update()
    
    def show_error_dialog(title: str, message: str):
        """Show error dialog"""
        def close_dlg(e):
            dlg_modal.open = False
            page.update()
        
        dlg_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, color=COLORS["error"], weight="bold"),
            content=ft.Text(message, color=COLORS["text"]),
            actions=[
                ft.TextButton("OK", on_click=close_dlg)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.dialog = dlg_modal
        dlg_modal.open = True
        page.update()
    
    def show_copy_dialog(title: str, code: str):
        """Show dialog with code user can copy manually"""
        def close_dlg(e):
            dlg_modal.open = False
            page.update()
        
        copy_field = ft.TextField(
            value=code,
            read_only=True,
            text_style=ft.TextStyle(size=18, weight="bold"),
            text_align=ft.TextAlign.CENTER,
            bgcolor=COLORS["secondary"],
        )
        
        dlg_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, color=COLORS["primary"]),
            content=ft.Column([
                ft.Text("Select and copy (Ctrl+C / Cmd+C):", size=12),
                copy_field,
                ft.Text("Share this code", size=12, italic=True, color=COLORS["text_secondary"]),
            ], tight=True, spacing=10),
            actions=[ft.TextButton("Done", on_click=close_dlg)],
        )
        
        page.dialog = dlg_modal
        dlg_modal.open = True
        page.update()
    
    def update_appbar():
        """Update AppBar with current user"""
        if config.CURRENT_USER_ID and current_user_data.get('display_name'):
            page.appbar = ft.AppBar(
                title=ft.Text(f"👤 {current_user_data['display_name']}", size=16),
                center_title=False,
                bgcolor=COLORS["primary"],
                color=COLORS["surface"],
                actions=[
                    ft.IconButton(
                        icon=ft.Icons.LOGOUT,
                        icon_color=COLORS["surface"],
                        tooltip="Logout",
                        on_click=logout_user
                    )
                ]
            )
        else:
            page.appbar = None
        page.update()
    
    # ==================== LOAD DATA ====================
    
    def load_trips():
        """Load user's trips"""
        nonlocal all_trips
        
        if not config.CURRENT_USER_ID:
            return
        
        try:
            response = db.get_user_trips(config.CURRENT_USER_ID)
            
            all_trips.clear()
            for row in response.data:
                trip = row['trips']
                if trip:
                    all_trips[trip['id']] = {
                        'name': trip['name'],
                        'is_active': trip['is_active'],
                        'invite_code': trip['invite_code'],
                        'created_by': trip.get('created_by')
                    }
            
            update_trip_list()
        except Exception as e:
            print(f"Error loading trips: {e}")
    
    def load_participants():
        """Load trip participants with nicknames"""
        nonlocal all_participants
        
        if not config.CURRENT_TRIP_ID:
            return
        
        try:
            response = db.get_trip_participants(config.CURRENT_TRIP_ID)
            
            all_participants.clear()
            for row in response.data:
                user = row['users']
                all_participants[user['id']] = {
                    'display_name': user['display_name'],
                    'email': user['email'],
                    'is_temp': user['is_temp'],
                    'claim_code': user['claim_code'],
                    'display_name_override': row.get('display_name_override')  # Trip-specific nickname
                }
            
            # Update all module views
            update_paid_by_dropdown()
            update_participant_checkboxes()
            update_participant_list()
            
        except Exception as e:
            print(f"Error loading participants: {e}")
    
    # ==================== TRIP MANAGEMENT ====================
    
    txt_trip_name = ft.TextField(
        label="Trip Name",
        hint_text="Baguio - Jan 2026",
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
        on_submit=lambda e: create_trip(e),  # Enter key
    )
    
    def create_trip(e):
        """Create new trip"""
        if not txt_trip_name.value:
            show_snackbar("Please enter trip name", error=True)
            return
        
        try:
            invite_code = generate_invite_code()
            
            # Create trip with creator
            response = db.create_trip(txt_trip_name.value, invite_code, config.CURRENT_USER_ID)
            
            new_trip = response.data[0]
            trip_id = new_trip['id']
            
            # Add current user to trip
            if config.CURRENT_USER_ID:
                db.add_user_to_trip(trip_id, config.CURRENT_USER_ID)
            
            all_trips[trip_id] = {
                'name': new_trip['name'],
                'is_active': new_trip['is_active'],
                'invite_code': new_trip['invite_code'],
                'created_by': new_trip.get('created_by', config.CURRENT_USER_ID)
            }
            
            txt_trip_name.value = ""
            
            # Auto-select the new trip
            select_trip(trip_id)
            
            update_trip_list()
            show_snackbar(f"✓ Trip created! Code: {invite_code}")
            
        except Exception as ex:
            print(f"Error creating trip: {ex}")
            show_error_dialog("Error", f"Failed to create trip: {str(ex)}")
    
    btn_create_trip = ft.Button(
        "Create Trip",
        on_click=create_trip,
        style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"]),
        width=200
    )
    
    # JOIN TRIP FEATURE (FIX #1)
    txt_join_code = ft.TextField(
        label="Trip Invite Code",
        hint_text="TRIP-ABC123",
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
        on_submit=lambda e: join_trip(e),  # Enter key
    )
    
    def join_trip(e):
        """Join trip using invite code"""
        if not txt_join_code.value:
            show_error_dialog("Code Required", "Please enter a trip invite code")
            return
        
        code = txt_join_code.value.strip().upper()
        
        try:
            trip_response = db.get_trip_by_invite_code(code)
            
            if not trip_response.data:
                show_error_dialog("Invalid Code", f"No trip found with code: {code}")
                return
            
            trip = trip_response.data[0]
            trip_id = trip['id']
            
            # Check if already member
            member_check = db.check_trip_membership(trip_id, config.CURRENT_USER_ID)
            
            if member_check.data:
                show_snackbar("Already a member of this trip!", error=True)
                return
            
            # Add to trip
            db.add_user_to_trip(trip_id, config.CURRENT_USER_ID)
            load_trips()
            select_trip(trip_id)
            
            txt_join_code.value = ""
            show_snackbar(f"✓ Joined trip: {trip['name']}")
            
        except Exception as ex:
            print(f"Join error: {ex}")
            show_error_dialog("Error", f"Failed to join trip: {str(ex)}")
    
    btn_join_trip = ft.Button(
        "Join Trip",
        on_click=join_trip,
        style=ft.ButtonStyle(bgcolor=COLORS["success"], color=COLORS["surface"]),
        width=200
    )
    
    def select_trip(trip_id: str):
        """Select active trip"""
        config.CURRENT_TRIP_ID = trip_id
        config.CURRENT_TRIP_CREATOR = all_trips[trip_id].get('created_by')
        save_session()
        load_participants()
        show_snackbar(f"✓ Switched to {all_trips[trip_id]['name']}")
        page.navigation_bar.selected_index = 0
        on_nav_change_internal(0)
    
    def archive_trip(trip_id: str):
        """Archive trip"""
        active_count = sum(1 for data in all_trips.values() if data['is_active'])
        
        if active_count <= 1:
            show_error_dialog("Cannot Archive", "Cannot archive the last active trip!")
            return
        
        if trip_id == config.CURRENT_TRIP_ID:
            for tid, data in all_trips.items():
                if tid != trip_id and data['is_active']:
                    select_trip(tid)
                    break
        
        try:
            db.archive_trip(trip_id)
            all_trips[trip_id]['is_active'] = False
            update_trip_list()
            show_snackbar("✓ Trip archived")
        except Exception as ex:
            print(f"Error: {ex}")
            show_error_dialog("Error", f"Failed to archive trip: {str(ex)}")
    
    def delete_trip(trip_id: str):
        """Delete trip (only if creator and alone OR all agree)"""
        try:
            # Get trip members
            members_response = db.get_trip_participants(trip_id)
            member_count = len(members_response.data)
            
            if member_count == 1:
                # Alone in trip - can delete
                def confirm_delete(e):
                    try:
                        # Delete trip
                        db.delete_trip(trip_id)
                        
                        # Remove from local state
                        if trip_id in all_trips:
                            del all_trips[trip_id]
                        
                        # Switch to another trip if this was current
                        if trip_id == config.CURRENT_TRIP_ID:
                            config.CURRENT_TRIP_ID = None
                            if all_trips:
                                first_trip = next(iter(all_trips.keys()))
                                select_trip(first_trip)
                        
                        update_trip_list()
                        show_snackbar("✓ Trip deleted")
                        
                        # Close dialog
                        confirm_dlg.open = False
                        page.update()
                        
                    except Exception as ex:
                        print(f"Delete error: {ex}")
                        show_error_dialog("Error", f"Failed to delete: {str(ex)}")
                
                def cancel_delete(e):
                    confirm_dlg.open = False
                    page.update()
                
                confirm_dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Delete Trip?", color=COLORS["error"], weight="bold"),
                    content=ft.Text("This will permanently delete the trip and all expenses. Continue?"),
                    actions=[
                        ft.TextButton("Cancel", on_click=cancel_delete),
                        ft.TextButton("Delete", on_click=confirm_delete, style=ft.ButtonStyle(color=COLORS["error"])),
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                
                page.dialog = confirm_dlg
                confirm_dlg.open = True
                page.update()
            else:
                # Multiple members - need collective agreement (future feature)
                show_error_dialog(
                    "Cannot Delete",
                    f"This trip has {member_count} members. Trip deletion requires all members to agree.\n\n(Feature coming soon: voting system)"
                )
                
        except Exception as ex:
            print(f"Error: {ex}")
            show_error_dialog("Error", f"Failed to check permissions: {str(ex)}")
    
    lv_trips = ft.ListView(expand=True, spacing=10, height=400)
    
    def update_trip_list():
        """Update trip list UI"""
        lv_trips.controls.clear()
        
        if not all_trips:
            lv_trips.controls.append(
                ft.Text("No trips yet. Create or join one below!", italic=True, color=COLORS["text_secondary"])
            )
        else:
            active_trips = [tid for tid, data in all_trips.items() if data['is_active']]
            
            if active_trips:
                lv_trips.controls.append(
                    ft.Text("Active Trips", weight="bold", size=16, color=COLORS["primary"])
                )
                for trip_id in active_trips:
                    trip = all_trips[trip_id]
                    is_current = trip_id == config.CURRENT_TRIP_ID
                    
                    def copy_invite(e, code=trip['invite_code']):
                        show_copy_dialog("Trip Invite Code", code)
                    
                    lv_trips.controls.append(
                        ft.Container(
                            content=ft.ListTile(
                                title=ft.Text(trip['name'], weight="bold", color=COLORS["text"]),
                                subtitle=ft.Text(f"Code: {trip['invite_code']}", color=COLORS["text_secondary"], selectable=True),
                                leading=ft.Icon(ft.Icons.CHECK_CIRCLE, color=COLORS["success"]) if is_current else ft.Icon(ft.Icons.LUGGAGE, color=COLORS["primary"]),
                                trailing=ft.Row([
                                    ft.IconButton(icon=ft.Icons.COPY, tooltip="Copy code", on_click=copy_invite, icon_color=COLORS["accent"], icon_size=16),
                                    ft.IconButton(icon=ft.Icons.ARROW_FORWARD, tooltip="Switch", on_click=lambda e, tid=trip_id: select_trip(tid), icon_color=COLORS["accent"]) if not is_current else ft.Container(width=40),
                                    ft.IconButton(icon=ft.Icons.ARCHIVE, tooltip="Archive", on_click=lambda e, tid=trip_id: archive_trip(tid), icon_color=COLORS["warning"]),
                                    ft.IconButton(icon=ft.Icons.DELETE, tooltip="Delete", on_click=lambda e, tid=trip_id: delete_trip(tid), icon_color=COLORS["error"]),
                                ], tight=True, spacing=0),
                            ),
                            bgcolor=COLORS["secondary"] if is_current else COLORS["surface"],
                            border_radius=8,
                            padding=5,
                            margin=ft.margin.only(bottom=10)
                        )
                    )
        
        page.update()
    
    def logout_user(e):
        """Logout and clear all state"""
        config.CURRENT_USER_ID = None
        config.CURRENT_TRIP_ID = None
        config.CURRENT_TRIP_CREATOR = None
        config.LOCAL_EXPENSES.clear()
        config.LAST_SELECTED_PARTICIPANTS.clear()
        config.SHOW_OFFLINE_PREVIEW = False
        
        current_user_data.clear()
        all_participants.clear()
        all_trips.clear()
        
        try:
            page.client_storage.clear()
        except:
            pass
        
        page.appbar = None
        welcome_container.visible = True
        main_container.visible = False
        page.navigation_bar.visible = False
        page.update()
        
        show_snackbar("✓ Logged out")
    
    # Continue with simplified implementation...
    # I'll provide remaining modules separately due to length
    
    view_trips = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text("Trips", size=24, weight="bold", color=COLORS["primary"]),
                padding=20,
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("My Trips", weight="bold", size=18, color=COLORS["text"]),
                    lv_trips,
                ]),
                padding=20,
                bgcolor=COLORS["surface"],
                border_radius=10,
                margin=10,
            ),
            # Create and Join side-by-side
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Create New Trip", weight="bold", size=18, color=COLORS["text"]),
                        txt_trip_name,
                        btn_create_trip,
                        ft.Text("Share invite code with friends", size=12, italic=True, color=COLORS["text_secondary"]),
                    ]),
                    padding=20,
                    bgcolor=COLORS["surface"],
                    border_radius=10,
                    margin=10,
                    expand=1,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Join Existing Trip", weight="bold", size=18, color=COLORS["text"]),
                        txt_join_code,
                        btn_join_trip,
                        ft.Text("Enter invite code from organizer", size=12, italic=True, color=COLORS["text_secondary"]),
                    ]),
                    padding=20,
                    bgcolor=COLORS["surface"],
                    border_radius=10,
                    margin=10,
                    expand=1,
                ),
            ], spacing=0),
        ], scroll="auto"),
        padding=0,
    )
    
    # ==================== CREATE MODULE VIEWS ====================
    
    # Show copy code dialog (used by multiple modules)
    def show_copy_code(title: str, code: str):
        """Show copyable code dialog"""
        def close_dlg(e):
            dlg_modal.open = False
            page.update()
        
        copy_field = ft.TextField(
            value=code,
            read_only=True,
            text_style=ft.TextStyle(size=18, weight="bold"),
            text_align=ft.TextAlign.CENTER,
            bgcolor=COLORS["secondary"],
        )
        
        dlg_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, color=COLORS["primary"]),
            content=ft.Column([
                ft.Text("Select and copy (Ctrl+C / Cmd+C):", size=12),
                copy_field,
                ft.Text("Share this code", size=12, italic=True, color=COLORS["text_secondary"]),
            ], tight=True, spacing=10),
            actions=[ft.TextButton("Done", on_click=close_dlg)],
        )
        
        page.dialog = dlg_modal
        dlg_modal.open = True
        page.update()
    
    # Create module views
    view_expenses, update_participant_checkboxes, update_paid_by_dropdown, update_unsynced_view = create_expenses_view(
        page, all_participants, show_snackbar, show_error_dialog
    )
    
    def on_participants_changed():
        """Called when participants are added/changed"""
        update_paid_by_dropdown()
        update_participant_checkboxes()
    
    view_participants, update_participant_list = create_participants_view(
        page, all_participants, show_snackbar, show_error_dialog, show_copy_code, on_participants_changed
    )
    
    view_dashboard, refresh_dashboard = create_dashboard_view(
        page, all_participants, show_snackbar, show_error_dialog
    )
    
    # ==================== NAVIGATION ====================
    
    body_container = ft.Container(content=view_expenses, expand=True)
    
    def on_nav_change(e):
        on_nav_change_internal(e.control.selected_index)
    
    def on_nav_change_internal(index):
        if index == 0:
            body_container.content = view_expenses
            update_unsynced_view()  # Refresh unsynced count
        elif index == 1:
            body_container.content = view_dashboard
            refresh_dashboard(None)  # Auto-refresh dashboard
        elif index == 2:
            body_container.content = view_participants
        else:
            body_container.content = view_trips
        page.update()
    
    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.ADD_CIRCLE, label="Add Expense"),
            ft.NavigationBarDestination(icon=ft.Icons.DASHBOARD, label="Dashboard"),
            ft.NavigationBarDestination(icon=ft.Icons.PEOPLE, label="Participants"),
            ft.NavigationBarDestination(icon=ft.Icons.LUGGAGE, label="Trips"),
        ],
        on_change=on_nav_change,
        bgcolor=COLORS["surface"],
        indicator_color=COLORS["secondary"],
        visible=False
    )
    
    # ==================== AUTH CALLBACK ====================
    
    def on_auth_success(user):
        """Called after successful authentication"""
        current_user_data['id'] = user['id']
        current_user_data['display_name'] = user['display_name']
        current_user_data['email'] = user['email']
        
        save_session()
        load_trips()
        
        # Auto-select most recent trip if available
        if all_trips and not config.CURRENT_TRIP_ID:
            # Get most recent trip (first in dict since load_trips loads in order)
            latest_trip_id = next(iter(all_trips))
            select_trip(latest_trip_id)
        elif config.CURRENT_TRIP_ID:
            # Refresh participants for current trip
            load_participants()
        else:
            # No trips - clear participants
            all_participants.clear()
            update_paid_by_dropdown()
            update_participant_checkboxes()
            update_participant_list()
        
        update_appbar()
        
        welcome_container.visible = False
        main_container.visible = True
        page.navigation_bar.visible = True
        page.update()
    
    # ==================== SETUP ====================
    
    welcome_container = create_auth_view(page, on_auth_success)
    main_container = ft.Container(content=body_container, expand=True, visible=False)
    
    page.add(ft.Stack([main_container, welcome_container], expand=True))
    
    # Check session
    if load_session() and config.CURRENT_USER_ID:
        try:
            response = db.get_user_by_id(config.CURRENT_USER_ID)
            if response.data:
                user = response.data[0]
                on_auth_success(user)
        except:
            pass


ft.app(main, view=ft.AppView.WEB_BROWSER, port=config.APP_PORT)