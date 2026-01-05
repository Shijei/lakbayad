"""
Participants Module - Participant management
"""
import flet as ft
import config
from config import COLORS
from database import db
from utils import generate_claim_code, normalize_name
from .helpers import show_snackbar, show_error_dialog


class ParticipantsComponent:
    """Component for managing participants"""
    
    def show_dialog(self, page: ft.Page, all_participants: dict, refresh_callback):
        """
        Show participants management dialog
        
        Args:
            page: Flet page instance
            all_participants: Dict of participants
            refresh_callback: Function to refresh dashboard
        """
        self.page = page
        self.all_participants = all_participants
        self.refresh_callback = refresh_callback
        
        lv_participants = ft.ListView(spacing=8, height=300)
        
        is_creator = config.CURRENT_TRIP_CREATOR == config.CURRENT_USER_ID
        
        for user_id, user_data in all_participants.items():
            is_you = user_id == config.CURRENT_USER_ID
            name = user_data.get('display_name_override') or user_data.get('display_name', 'Unknown')
            
            display_text = f"{name} (You)" if is_you else name
            
            trailing_btns = []
            
            if is_creator and not is_you:
                # Edit nickname button
                def make_edit_handler(uid, current_nick, actual_name):
                    def handler(e):
                        self._show_edit_nickname_dialog(uid, current_nick, actual_name)
                    return handler
                
                trailing_btns.append(ft.IconButton(
                    icon=ft.Icons.EDIT,
                    icon_size=18,
                    icon_color=COLORS["accent"],
                    tooltip="Edit nickname",
                    on_click=make_edit_handler(user_id, user_data.get('display_name_override'), user_data['display_name'])
                ))
                
                # Remove button
                def make_remove_handler(uid, uname):
                    def handler(e):
                        self._confirm_remove_participant(uid, uname)
                    return handler
                
                trailing_btns.append(ft.IconButton(
                    icon=ft.Icons.PERSON_REMOVE,
                    icon_size=18,
                    icon_color=COLORS["error"],
                    tooltip="Remove from trip",
                    on_click=make_remove_handler(user_id, name)
                ))
            
            lv_participants.controls.append(
                ft.Container(
                    content=ft.ListTile(
                        title=ft.Text(display_text, size=14, weight="w500"),
                        trailing=ft.Row(trailing_btns, spacing=4, tight=True) if trailing_btns else None,
                    ),
                    bgcolor=COLORS["secondary"] if is_you else COLORS["surface"],
                    border_radius=12,
                    padding=4,
                    margin=ft.margin.only(bottom=4),
                )
            )
        
        def close_participants(e):
            participants_dlg.open = False
            page.update()
        
        def add_participant(e):
            participants_dlg.open = False
            page.update()
            self._show_add_participant_dialog()
        
        participants_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("👥 Participants", size=20, weight="bold"),
            content=lv_participants,
            actions=[
                ft.ElevatedButton(
                    "➕ Add Participant",
                    on_click=add_participant,
                    style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"])
                ),
                ft.TextButton("Close", on_click=close_participants)
            ]
        )
        
        page.dialog = participants_dlg
        participants_dlg.open = True
        page.update()
    
    def _show_add_participant_dialog(self):
        """Show add participant dialog"""
        txt_name = ft.TextField(label="Name", autofocus=True, border_radius=12)
        txt_email = ft.TextField(label="Email (optional)", keyboard_type=ft.KeyboardType.EMAIL, border_radius=12)
        
        def save_participant(e):
            if not txt_name.value:
                show_error_dialog(self.page, "Missing Name", "Please enter a name")
                return
            
            try:
                display_name = txt_name.value.strip()
                email = txt_email.value.strip().lower() if txt_email.value else None
                
                # Check duplicate
                normalized = normalize_name(display_name)
                for user_data in self.all_participants.values():
                    if normalize_name(user_data['display_name']) == normalized:
                        show_error_dialog(self.page, "Duplicate", f"{display_name} already exists!")
                        return
                
                # Check if user exists by email
                if email:
                    check = db.get_user_by_email(email)
                    if check.data:
                        existing = check.data[0]
                        user_id = existing['id']
                        
                        if user_id in self.all_participants:
                            show_error_dialog(self.page, "Already Added", "This user is already in the trip!")
                            return
                        
                        db.add_user_to_trip(config.CURRENT_TRIP_ID, user_id)
                        self.all_participants[user_id] = {
                            'display_name': existing['display_name'],
                            'email': existing['email'],
                            'is_temp': existing['is_temp'],
                            'claim_code': existing['claim_code'],
                            'display_name_override': None
                        }
                        
                        show_snackbar(self.page, f"✓ Added {display_name}!")
                        add_dlg.open = False
                        self.page.update()
                        self.refresh_callback(None)
                        return
                
                # Create temp user
                claim_code = generate_claim_code(display_name)
                response = db.create_user(None, display_name, "", claim_code, is_temp=True)
                user = response.data[0]
                user_id = user['id']
                
                db.add_user_to_trip(config.CURRENT_TRIP_ID, user_id)
                self.all_participants[user_id] = {
                    'display_name': user['display_name'],
                    'email': None,
                    'is_temp': True,
                    'claim_code': claim_code,
                    'display_name_override': None
                }
                
                show_snackbar(self.page, f"✓ Added {display_name}!")
                add_dlg.open = False
                self.page.update()
                self.refresh_callback(None)
                
            except Exception as ex:
                show_error_dialog(self.page, "Error", str(ex))
        
        def cancel(e):
            add_dlg.open = False
            self.page.update()
        
        add_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add Participant", size=20, weight="bold"),
            content=ft.Column([txt_name, txt_email], tight=True, spacing=12),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton("Add", on_click=save_participant,
                                 style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"])),
            ]
        )
        self.page.dialog = add_dlg
        add_dlg.open = True
        self.page.update()
    
    def _show_edit_nickname_dialog(self, user_id: str, current_nick: str, actual_name: str):
        """Show edit nickname dialog"""
        txt_nick = ft.TextField(
            label=f"Nickname for {actual_name}", 
            value=current_nick or "",
            border_radius=12
        )
        
        def save(e):
            try:
                new_nick = txt_nick.value.strip()
                if new_nick:
                    db.update_participant_nickname(config.CURRENT_TRIP_ID, user_id, new_nick)
                else:
                    db.clear_participant_nickname(config.CURRENT_TRIP_ID, user_id)
                
                self.all_participants[user_id]['display_name_override'] = new_nick if new_nick else None
                show_snackbar(self.page, "✓ Updated")
                edit_dlg.open = False
                self.page.update()
                # Reopen participants dialog
                self.show_dialog(self.page, self.all_participants, self.refresh_callback)
            except Exception as ex:
                show_error_dialog(self.page, "Error", str(ex))
        
        def cancel(e):
            edit_dlg.open = False
            self.page.update()
        
        edit_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Nickname"),
            content=txt_nick,
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton("Save", on_click=save,
                                 style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"])),
            ]
        )
        self.page.dialog = edit_dlg
        edit_dlg.open = True
        self.page.update()
    
    
    def _confirm_remove_participant(self, user_id: str, user_name: str):
        """Confirm and remove participant with CASCADE DELETE"""
        
        # Check if user has related expenses
        has_expenses = False
        expense_count = 0
        try:
            response = db.get_trip_expenses(config.CURRENT_TRIP_ID)
            for expense in response.data:
                if expense['paid_by_id'] == user_id:
                    has_expenses = True
                    expense_count += 1
                else:
                    for participant in expense.get('expense_participants', []):
                        if participant['user_id'] == user_id:
                            has_expenses = True
                            expense_count += 1
                            break
        except Exception as ex:
            print(f"Expense check error: {ex}")
        
        warning_text = f"Remove {user_name} from this trip?"
        if has_expenses:
            warning_text += f"\n\n⚠️ WARNING: {expense_count} expense(s) involving {user_name} will be DELETED!"
        
        def confirm(e):
            try:
                # Delete related expenses FIRST
                if has_expenses:
                    response = db.get_trip_expenses(config.CURRENT_TRIP_ID)
                    for expense in response.data:
                        should_delete = False
                        
                        # Check if user paid for it
                        if expense['paid_by_id'] == user_id:
                            should_delete = True
                        else:
                            # Check if user is a participant
                            for participant in expense.get('expense_participants', []):
                                if participant['user_id'] == user_id:
                                    should_delete = True
                                    break
                        
                        if should_delete:
                            try:
                                db.delete_expense(expense['id'])
                            except Exception as del_ex:
                                print(f"Delete expense error: {del_ex}")
                
                # NOW remove from trip
                db.remove_participant(config.CURRENT_TRIP_ID, user_id)
                del self.all_participants[user_id]
                
                show_snackbar(self.page, f"✓ Removed {user_name}")
                confirm_dlg.open = False
                self.page.update()
                
                # Reopen participants dialog and refresh dashboard
                self.show_dialog(self.page, self.all_participants, self.refresh_callback)
                self.refresh_callback(None)
                
            except Exception as ex:
                show_error_dialog(self.page, "Error", str(ex))
        
        def cancel(e):
            confirm_dlg.open = False
            self.page.update()
        
        confirm_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Remove Participant?", 
                         color=COLORS["error"] if has_expenses else COLORS["text"]),
            content=ft.Text(warning_text),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.TextButton("Remove", on_click=confirm,
                             style=ft.ButtonStyle(color=COLORS["error"])),
            ]
        )
        self.page.dialog = confirm_dlg
        confirm_dlg.open = True
        self.page.update()