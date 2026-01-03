"""
Participants Module - Manage trip participants with creator controls
"""
import flet as ft
import config
from config import COLORS
from database import db
from utils import generate_claim_code, normalize_name


def create_participants_view(page: ft.Page, all_participants: dict, show_snackbar, show_error, show_copy_code, on_participants_changed=None):
    """Create participants management view with edit/remove for creators"""
    
    # UI Components
    txt_new_participant = ft.TextField(
        label="Participant Name",
        hint_text="John Doe",
        width=300,
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
    )
    
    txt_participant_email = ft.TextField(
        label="Email (Optional)",
        hint_text="john@email.com",
        keyboard_type=ft.KeyboardType.EMAIL,
        width=300,
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
    )
    
    lv_participants = ft.ListView(expand=True, spacing=10, height=400)
    
    def add_participant(e):
        """Add new participant"""
        if not config.CURRENT_TRIP_ID:
            show_error("No Trip", "Please select or create a trip first!")
            return
        
        if not txt_new_participant.value:
            show_error("Missing Name", "Please enter a name")
            return
        
        display_name = txt_new_participant.value.strip()
        email = txt_participant_email.value.strip().lower() if txt_participant_email.value else None
        
        # Check if name already exists in THIS trip (case-insensitive)
        normalized_new = normalize_name(display_name)
        for user_data in all_participants.values():
            if normalize_name(user_data['display_name']) == normalized_new:
                show_error("Duplicate Name", f"{display_name} is already in this trip!")
                return
        
        try:
            # Check if email already exists in database
            if email:
                check_response = db.get_user_by_email(email)
                if check_response.data:
                    # User exists - just add them to trip
                    existing_user = check_response.data[0]
                    user_id = existing_user['id']
                    
                    # Check if already in trip
                    if user_id in all_participants:
                        show_error("Already Added", f"{display_name} is already in this trip!")
                        return
                    
                    # Add to trip
                    db.add_user_to_trip(config.CURRENT_TRIP_ID, user_id)
                    
                    # Add to local dict
                    all_participants[user_id] = {
                        'display_name': existing_user['display_name'],
                        'email': existing_user['email'],
                        'is_temp': existing_user['is_temp'],
                        'claim_code': existing_user['claim_code'],
                        'display_name_override': None
                    }
                    
                    config.LAST_SELECTED_PARTICIPANTS.add(user_id)
                    
                    txt_new_participant.value = ""
                    txt_participant_email.value = ""
                    
                    update_participant_list()
                    
                    # Notify other modules
                    if on_participants_changed:
                        on_participants_changed()
                    
                    show_snackbar(f"✓ Added existing user {display_name}!")
                    return
            
            # Create new temp user (NO EMAIL until they claim)
            claim_code = generate_claim_code(display_name)
            
            user_response = db.create_user(
                email=None,  # No email for temp users - they add it when claiming
                display_name=display_name,
                password_hash="",  # Temp user, no password
                claim_code=claim_code,
                is_temp=True  # Temporary until they claim
            )
            
            user = user_response.data[0]
            user_id = user['id']
            
            # Add to current trip
            db.add_user_to_trip(config.CURRENT_TRIP_ID, user_id)
            
            # Add to local dict
            all_participants[user_id] = {
                'display_name': user['display_name'],
                'email': user['email'],
                'is_temp': user['is_temp'],
                'claim_code': user['claim_code'],
                'display_name_override': None
            }
            
            # Add to last selected participants (auto-include in splits)
            config.LAST_SELECTED_PARTICIPANTS.add(user_id)
            
            # Clear form
            txt_new_participant.value = ""
            txt_participant_email.value = ""
            
            update_participant_list()
            
            # Notify other modules
            if on_participants_changed:
                on_participants_changed()
            
            show_snackbar(f"✓ Added {display_name} with code: {claim_code}")
            
        except Exception as ex:
            print(f"Error adding participant: {ex}")
            show_error("Error", f"Failed to add participant: {str(ex)}")
    
    btn_add_participant = ft.Button(
        "Add Participant",
        on_click=add_participant,
        style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"]),
        width=300
    )
    
    def update_participant_list():
        """Update participant list with edit/remove controls for creators"""
        lv_participants.controls.clear()
        
        if not all_participants:
            lv_participants.controls.append(
                ft.Text("No participants yet", italic=True, color=COLORS["text_secondary"])
            )
        else:
            is_creator = config.CURRENT_TRIP_CREATOR == config.CURRENT_USER_ID
            
            for user_id, user_data in all_participants.items():
                is_current_user = user_id == config.CURRENT_USER_ID
                display_name = user_data.get('display_name', 'Unknown')
                nickname = user_data.get('display_name_override')  # Trip-specific nickname
                email = user_data.get('email') or 'No email'
                is_temp = user_data.get('is_temp', False)
                claim_code = user_data.get('claim_code', '')
                
                # Use nickname if set, otherwise actual name
                shown_name = nickname if nickname else display_name
                
                # Status
                if is_temp:
                    icon = ft.Icons.PERSON_OUTLINE
                    status_text = "⏳ Pending Claim"
                    icon_color = COLORS["warning"]
                else:
                    icon = ft.Icons.PERSON
                    status_text = "✓ Verified"
                    icon_color = COLORS["success"]
                
                # Build trailing controls for creator
                trailing_controls = []
                
                # Edit nickname button (creator only, not for self)
                if is_creator and not is_current_user:
                    def make_edit_handler(uid, current_nick, actual_name):
                        def handler(e):
                            txt_nickname = ft.TextField(
                                label=f"Nickname for {actual_name}",
                                value=current_nick if current_nick else "",
                                hint_text=f"Leave empty to use '{actual_name}'",
                                autofocus=True,
                            )
                            
                            def save_nickname(e):
                                new_nick = txt_nickname.value.strip()
                                try:
                                    if new_nick:
                                        db.update_participant_nickname(config.CURRENT_TRIP_ID, uid, new_nick)
                                    else:
                                        db.clear_participant_nickname(config.CURRENT_TRIP_ID, uid)
                                    
                                    # Update local data
                                    all_participants[uid]['display_name_override'] = new_nick if new_nick else None
                                    
                                    # Reload participants
                                    update_participant_list()
                                    
                                    # Notify other modules
                                    if on_participants_changed:
                                        on_participants_changed()
                                    
                                    show_snackbar(f"✓ Nickname updated!")
                                except Exception as ex:
                                    show_error("Error", f"Failed to update nickname: {str(ex)}")
                                
                                dlg.open = False
                                page.update()
                            
                            def cancel(e):
                                dlg.open = False
                                page.update()
                            
                            dlg = ft.AlertDialog(
                                modal=True,
                                title=ft.Text("Edit Nickname", color=COLORS["primary"]),
                                content=txt_nickname,
                                actions=[
                                    ft.TextButton("Cancel", on_click=cancel),
                                    ft.TextButton("Save", on_click=save_nickname),
                                ],
                            )
                            page.dialog = dlg
                            dlg.open = True
                            page.update()
                        return handler
                    
                    trailing_controls.append(
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            icon_color=COLORS["accent"],
                            icon_size=18,
                            tooltip="Edit nickname for this trip",
                            on_click=make_edit_handler(user_id, nickname, display_name)
                        )
                    )
                
                # Remove button (creator only, not for self)
                if is_creator and not is_current_user:
                    def make_remove_handler(uid, name):
                        def handler(e):
                            def confirm_remove(e):
                                try:
                                    db.remove_participant(config.CURRENT_TRIP_ID, uid)
                                    
                                    # Remove from local dict
                                    del all_participants[uid]
                                    
                                    # Update UI
                                    update_participant_list()
                                    
                                    # Notify other modules
                                    if on_participants_changed:
                                        on_participants_changed()
                                    
                                    show_snackbar(f"✓ Removed {name}")
                                except Exception as ex:
                                    show_error("Error", f"Failed to remove: {str(ex)}")
                                
                                confirm_dlg.open = False
                                page.update()
                            
                            def cancel(e):
                                confirm_dlg.open = False
                                page.update()
                            
                            confirm_dlg = ft.AlertDialog(
                                modal=True,
                                title=ft.Text("Remove Participant?", color=COLORS["error"]),
                                content=ft.Text(f"Remove {name} from this trip?\n\nThey will lose access to this trip."),
                                actions=[
                                    ft.TextButton("Cancel", on_click=cancel),
                                    ft.TextButton("Remove", on_click=confirm_remove),
                                ],
                            )
                            page.dialog = confirm_dlg
                            confirm_dlg.open = True
                            page.update()
                        return handler
                    
                    trailing_controls.append(
                        ft.IconButton(
                            icon=ft.Icons.PERSON_REMOVE,
                            icon_color=COLORS["error"],
                            icon_size=18,
                            tooltip="Remove from trip",
                            on_click=make_remove_handler(user_id, shown_name)
                        )
                    )
                
                # Copy claim code button (for temp users)
                if is_temp and claim_code:
                    trailing_controls.append(
                        ft.IconButton(
                            icon=ft.Icons.COPY,
                            icon_size=18,
                            tooltip="Copy claim code",
                            on_click=lambda e, code=claim_code: show_copy_code("Claim Code", code)
                        )
                    )
                
                # Build title with nickname indicator
                title_text = shown_name
                if nickname:
                    title_text += f" (real name: {display_name})"
                if is_current_user:
                    title_text += " (You)"
                
                subtitle_text = f"{email} • {status_text}"
                if is_temp and claim_code:
                    subtitle_text += f"\nClaim code: {claim_code}"
                
                tile = ft.ListTile(
                    leading=ft.Icon(icon, color=icon_color),
                    title=ft.Text(title_text, weight="bold", size=14),
                    subtitle=ft.Text(subtitle_text, size=12),
                    trailing=ft.Row(trailing_controls, spacing=5, tight=True) if trailing_controls else None,
                )
                
                lv_participants.controls.append(
                    ft.Container(
                        content=tile,
                        bgcolor=COLORS["secondary"] if is_current_user else COLORS["surface"],
                        border_radius=8,
                        padding=5,
                    )
                )
        
        page.update()
    
    # Main view
    view_participants = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text("Participants", size=24, weight="bold", color=COLORS["primary"]),
                padding=20,
            ),
            
            # Trip Members List
            ft.Container(
                content=ft.Column([
                    ft.Text("Trip Members", weight="bold", size=18, color=COLORS["text"]),
                    lv_participants,
                ]),
                padding=20,
                bgcolor=COLORS["surface"],
                border_radius=10,
                margin=10,
            ),
            
            # Add New Participant
            ft.Container(
                content=ft.Column([
                    ft.Text("Add New Participant", weight="bold", size=18, color=COLORS["text"]),
                    txt_new_participant,
                    txt_participant_email,
                    btn_add_participant,
                    ft.Text(
                        "💡 Tip: Share the claim code so they can access their account",
                        size=12,
                        italic=True,
                        color=COLORS["text_secondary"]
                    ),
                ]),
                padding=20,
                bgcolor=COLORS["surface"],
                border_radius=10,
                margin=10,
            ),
        ], scroll=ft.ScrollMode.AUTO),
        expand=True,
        bgcolor=COLORS["bg"],
    )
    
    return view_participants, update_participant_list