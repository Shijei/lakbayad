"""
Trip Selection Module - Create, join, and select trips (WITH DELETE/ARCHIVE)
"""
import flet as ft
import config
from config import COLORS
from database import db
from utils import generate_invite_code
from .helpers import show_snackbar, show_error_dialog, create_card_style


def create_trip_selection_view(page: ft.Page, all_trips: dict, all_participants: dict, 
                               on_trip_selected, show_snackbar_func, show_error_func):
    """
    Create trip selection/creation screen
    
    Args:
        page: Flet page instance
        all_trips: Dict of all user's trips
        all_participants: Dict of all participants (to be updated)
        on_trip_selected: Callback when trip is selected (trip_id, trip_name)
        show_snackbar_func: Snackbar function
        show_error_func: Error dialog function
    
    Returns:
        ft.Container with trip selection UI
    """
    
    lv_trips = ft.ListView(spacing=12, expand=True)
    
    def update_trip_list():
        """Refresh the trip list display"""
        lv_trips.controls.clear()
        
        if not all_trips:
            lv_trips.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.EXPLORE, size=64, color=COLORS["text_secondary"]),
                        ft.Text("No trips yet", size=18, color=COLORS["text_secondary"]),
                        ft.Text("Create or join a trip to get started", 
                               size=14, color=COLORS["text_secondary"], italic=True),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    padding=40,
                    alignment=ft.alignment.center,
                )
            )
        else:
            for trip_id, trip_data in all_trips.items():
                def make_select_handler(tid, tname):
                    def handler(e):
                        select_trip(tid, tname)
                    return handler
                
                def make_options_handler(tid, tname):
                    def handler(e):
                        show_trip_options(tid, tname)
                    return handler
                
                lv_trips.controls.append(
                    ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon(ft.Icons.TRIP_ORIGIN, size=32, color=COLORS["primary"]),
                            title=ft.Text(trip_data['name'], size=16, weight="bold"),
                            subtitle=ft.Text(f"Code: {trip_data['invite_code']}", size=12),
                            trailing=ft.Row([
                                ft.IconButton(
                                    icon=ft.Icons.MORE_VERT,
                                    icon_size=20,
                                    icon_color=COLORS["text_secondary"],
                                    tooltip="Trip options",
                                    on_click=make_options_handler(trip_id, trip_data['name'])
                                ),
                                ft.Icon(ft.Icons.ARROW_FORWARD, color=COLORS["accent"], size=20),
                            ], spacing=0, tight=True),
                            on_click=make_select_handler(trip_id, trip_data['name']),
                        ),
                        **create_card_style()
                    )
                )
        
        page.update()
    
    def select_trip(trip_id: str, trip_name: str):
        """Select a trip and load its participants"""
        try:
            # Load participants for this trip
            response = db.get_trip_participants(trip_id)
            all_participants.clear()
            
            for row in response.data:
                user = row['users']
                if user:
                    all_participants[user['id']] = {
                        'display_name': user['display_name'],
                        'email': user.get('email'),
                        'is_temp': user.get('is_temp', False),
                        'claim_code': user.get('claim_code'),
                        'display_name_override': row.get('display_name_override')
                    }
            
            # Set current trip and notify
            config.CURRENT_TRIP_ID = trip_id
            config.CURRENT_TRIP_CREATOR = all_trips[trip_id].get('created_by')
            
            on_trip_selected(trip_id, trip_name)
            
        except Exception as ex:
            print(f"Select trip error: {ex}")
            show_error_func("Error", f"Failed to load trip: {str(ex)}")
    
    def show_trip_options(trip_id: str, trip_name: str):
        """Show trip management options (delete/archive)"""
        is_creator = all_trips[trip_id].get('created_by') == config.CURRENT_USER_ID
        
        def archive_trip(e):
            try:
                db.archive_trip(trip_id)
                all_trips[trip_id]['is_active'] = False
                show_snackbar_func(f"✓ Archived {trip_name}")
                options_dlg.open = False
                page.update()
                update_trip_list()
            except Exception as ex:
                show_error_func("Error", str(ex))
        
        def delete_trip(e):
            def confirm_delete(e2):
                try:
                    db.delete_trip(trip_id)
                    del all_trips[trip_id]
                    show_snackbar_func(f"✓ Deleted {trip_name}")
                    confirm_dlg.open = False
                    options_dlg.open = False
                    page.update()
                    update_trip_list()
                except Exception as ex:
                    show_error_func("Error", str(ex))
            
            def cancel_delete(e2):
                confirm_dlg.open = False
                page.update()
            
            confirm_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Delete Trip?", color=COLORS["error"]),
                content=ft.Text(f"Permanently delete '{trip_name}'?\n\nThis will delete all expenses, settlements, and cannot be undone."),
                actions=[
                    ft.TextButton("Cancel", on_click=cancel_delete),
                    ft.TextButton("Delete", on_click=confirm_delete,
                                 style=ft.ButtonStyle(color=COLORS["error"])),
                ]
            )
            page.dialog = confirm_dlg
            confirm_dlg.open = True
            page.update()
        
        def close_options(e):
            options_dlg.open = False
            page.update()
        
        options = []
        if is_creator:
            options.extend([
                ft.ElevatedButton(
                    "🗄️ Archive Trip",
                    on_click=archive_trip,
                    style=ft.ButtonStyle(bgcolor=COLORS["warning"], color=COLORS["surface"]),
                    expand=True
                ),
                ft.Container(height=8),
                ft.ElevatedButton(
                    "🗑️ Delete Trip",
                    on_click=delete_trip,
                    style=ft.ButtonStyle(bgcolor=COLORS["error"], color=COLORS["surface"]),
                    expand=True
                ),
            ])
        else:
            options.append(ft.Text("Only trip creator can delete/archive trips", 
                                  size=12, italic=True, color=COLORS["text_secondary"]))
        
        options_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Trip Options: {trip_name}", size=18, weight="bold"),
            content=ft.Container(
                content=ft.Column(options, spacing=8, tight=True),
                width=300
            ),
            actions=[ft.TextButton("Close", on_click=close_options)]
        )
        page.dialog = options_dlg
        options_dlg.open = True
        page.update()
    
    def show_create_trip_dialog(e):
        """Show dialog to create new trip"""
        txt_name = ft.TextField(
            label="Trip Name",
            hint_text="Baguio Trip 2025",
            autofocus=True,
            border_radius=12
        )
        
        def create_trip(e):
            if not txt_name.value:
                show_error_func("Missing Name", "Please enter a trip name")
                return
            
            try:
                invite_code = generate_invite_code()
                response = db.create_trip(
                    txt_name.value.strip(), 
                    invite_code,
                    config.CURRENT_USER_ID
                )
                
                if response.data and len(response.data) > 0:
                    trip = response.data[0]
                    trip_id = trip['id']
                    
                    # Add creator to trip
                    db.add_user_to_trip(trip_id, config.CURRENT_USER_ID)
                    
                    # Update local trips dict
                    all_trips[trip_id] = {
                        'name': trip['name'],
                        'is_active': trip['is_active'],
                        'invite_code': trip['invite_code'],
                        'created_by': trip.get('created_by')
                    }
                    
                    show_snackbar_func(f"✓ Created trip: {trip['name']}")
                    create_dlg.open = False
                    page.update()
                    update_trip_list()
                    
            except Exception as ex:
                show_error_func("Error", str(ex))
        
        def cancel(e):
            create_dlg.open = False
            page.update()
        
        create_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Create New Trip", size=20, weight="bold"),
            content=txt_name,
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton(
                    "Create",
                    on_click=create_trip,
                    style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"])
                ),
            ]
        )
        
        page.dialog = create_dlg
        create_dlg.open = True
        page.update()
    
    def show_join_trip_dialog(e):
        """Show dialog to join existing trip"""
        txt_code = ft.TextField(
            label="Invite Code",
            hint_text="ABC123",
            autofocus=True,
            border_radius=12,
            max_length=6,
            text_transform=ft.TextTransform.UPPERCASE
        )
        
        def join_trip(e):
            if not txt_code.value:
                show_error_func("Missing Code", "Please enter an invite code")
                return
            
            try:
                code = txt_code.value.strip().upper()
                
                # Check if trip exists
                response = db.get_trip_by_invite_code(code)
                if not response.data:
                    show_error_func("Invalid Code", "No trip found with this code")
                    return
                
                trip = response.data[0]
                trip_id = trip['id']
                
                # Check if already member
                try:
                    membership = db.check_trip_membership(trip_id, config.CURRENT_USER_ID)
                    if membership.data and len(membership.data) > 0:
                        show_error_func("Already Joined", "You're already in this trip!")
                        return
                except:
                    # Method might not exist, skip check
                    pass
                
                # Add user to trip
                db.add_user_to_trip(trip_id, config.CURRENT_USER_ID)
                
                # Update local trips dict
                all_trips[trip_id] = {
                    'name': trip['name'],
                    'is_active': trip['is_active'],
                    'invite_code': trip['invite_code'],
                    'created_by': trip.get('created_by')
                }
                
                show_snackbar_func(f"✓ Joined trip: {trip['name']}")
                join_dlg.open = False
                page.update()
                update_trip_list()
                
            except Exception as ex:
                show_error_func("Error", str(ex))
        
        def cancel(e):
            join_dlg.open = False
            page.update()
        
        join_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Join Trip", size=20, weight="bold"),
            content=ft.Column([
                ft.Text("Enter the invite code shared by your trip organizer", size=12),
                ft.Container(height=8),
                txt_code,
            ], tight=True, spacing=8),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton(
                    "Join",
                    on_click=join_trip,
                    style=ft.ButtonStyle(bgcolor=COLORS["success"], color=COLORS["surface"])
                ),
            ]
        )
        
        page.dialog = join_dlg
        join_dlg.open = True
        page.update()
    
    # Initial load
    update_trip_list()
    
    # Build UI
    return ft.Container(
        content=ft.Column([
            # Header
            ft.Container(
                content=ft.Column([
                    ft.Text("🎒 My Trips", size=32, weight="bold", color=COLORS["primary"]),
                    ft.Text("Select a trip or create a new one", size=14, color=COLORS["text_secondary"]),
                ]),
                padding=20,
            ),
            
            # Trip list
            ft.Container(
                content=lv_trips,
                expand=True,
                padding=ft.padding.only(left=20, right=20, bottom=20),
            ),
            
            # Action buttons
            ft.Container(
                content=ft.Row([
                    ft.ElevatedButton(
                        "➕ Create Trip",
                        on_click=show_create_trip_dialog,
                        expand=True,
                        height=50,
                        style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"])
                    ),
                    ft.Container(width=12),
                    ft.ElevatedButton(
                        "🔗 Join Trip",
                        on_click=show_join_trip_dialog,
                        expand=True,
                        height=50,
                        style=ft.ButtonStyle(bgcolor=COLORS["accent"], color=COLORS["surface"])
                    ),
                ]),
                padding=20,
            ),
        ]),
        bgcolor=COLORS["bg"],
        expand=True,
    )