"""
Expenses Module - Expense management and display
"""
import flet as ft
import config
from config import COLORS
from database import db
from utils import format_currency, generate_claim_code, normalize_name
from .helpers import show_snackbar, show_error_dialog, create_card_style


class ExpensesComponent:
    """Component for managing expenses"""
    
    def __init__(self):
        self.lv_expenses = ft.ListView(spacing=8, height=300)
        self.chk_show_offline = ft.Checkbox(
            label="Show Unsynced", 
            value=True, 
            active_color=COLORS["accent"]
        )
        self.btn_sync = None  # Will be created in create_section()
    
    def create_section(self, page: ft.Page, all_participants: dict, refresh_callback):
        """
        Create expenses section UI
        
        Args:
            page: Flet page instance
            all_participants: Dict of participants
            refresh_callback: Function to refresh dashboard
        
        Returns:
            ft.Container with expenses section
        """
        self.page = page
        self.all_participants = all_participants
        self.refresh_callback = refresh_callback
        
        def on_checkbox_change(e):
            config.SHOW_OFFLINE_PREVIEW = self.chk_show_offline.value
            refresh_callback(None)
        
        self.chk_show_offline.on_change = on_checkbox_change
        
        # Sync button (stored as instance variable for dynamic updates)
        self.btn_sync = ft.ElevatedButton(
            "☁️ Sync to Cloud",
            on_click=self._sync_offline_expenses,
            style=ft.ButtonStyle(bgcolor=COLORS["accent"], color=COLORS["surface"], padding=16),
            height=50,
            visible=len(config.LOCAL_EXPENSES) > 0,
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("📝 Expenses", size=18, weight="bold"),
                    self.chk_show_offline,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=12),
                self.lv_expenses,
                ft.Container(height=12),
                ft.Row([
                    ft.ElevatedButton(
                        "➕ Add Expense",
                        on_click=lambda e: self._show_add_expense_dialog(),
                        style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"], padding=16),
                        expand=True,
                        height=50,
                    ),
                    ft.Container(width=8),
                    self.btn_sync,
                ], spacing=0),
            ]),
            **create_card_style()
        )
    
    def update_list(self, expenses_data: list, all_participants: dict):
        """Update expenses list display"""
        self.lv_expenses.controls.clear()
        
        # Update sync button visibility and text based on LOCAL_EXPENSES count
        unsynced_count = len(config.LOCAL_EXPENSES)
        if self.btn_sync:
            self.btn_sync.visible = unsynced_count > 0
            if unsynced_count > 0:
                self.btn_sync.text = f"☁️ Sync to Cloud ({unsynced_count})"
        
        if not expenses_data:
            self.lv_expenses.controls.append(
                ft.Container(
                    content=ft.Text("No expenses yet. Click Add Expense!", 
                                   italic=True, color=COLORS["text_secondary"], size=14),
                    padding=20,
                )
            )
        else:
            for exp in expenses_data:
                is_synced = exp.get('synced', True)
                paid_by_name = all_participants.get(exp['paid_by_id'], {}).get('display_name_override') or \
                               all_participants.get(exp['paid_by_id'], {}).get('display_name', 'Unknown')
                amount_str = format_currency(exp['amount_cents'])
                
                is_creator = exp['paid_by_id'] == config.CURRENT_USER_ID
                
                subtitle_text = f"{paid_by_name} • {amount_str}"
                if not is_synced:
                    subtitle_text += " • 🔴 Unsynced"
                
                # Delete button for creator
                trailing = None
                if is_creator and exp.get('id'):
                    def make_delete_handler(exp_id):
                        def handler(e):
                            self._confirm_delete_expense(exp_id)
                        return handler
                    
                    trailing = ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=COLORS["error"],
                        icon_size=18,
                        on_click=make_delete_handler(exp['id'])
                    )
                
                self.lv_expenses.controls.append(
                    ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon(ft.Icons.RECEIPT, size=20, 
                                          color=COLORS["warning"] if not is_synced else COLORS["accent"]),
                            title=ft.Text(exp['description'], size=14, weight="w500"),
                            subtitle=ft.Text(subtitle_text, size=12),
                            trailing=trailing,
                        ),
                        bgcolor=COLORS["secondary"] if not is_synced else COLORS["surface"],
                        border_radius=12,
                        padding=4,
                        margin=ft.margin.only(bottom=4),
                    )
                )
    
    def _show_add_expense_dialog(self):
        """Show add expense dialog"""
        # Paid by dropdown
        paid_by_options = []
        for user_id, user_data in self.all_participants.items():
            name = user_data.get('display_name_override') or user_data.get('display_name', 'Unknown')
            paid_by_options.append(ft.dropdown.Option(key=user_id, text=name))
        
        dropdown_paid_by = ft.Dropdown(
            label="Who paid?",
            border_radius=12,
            options=paid_by_options,
            value=config.CURRENT_USER_ID if config.CURRENT_USER_ID in self.all_participants else None,
        )
        
        dropdown_category = ft.Dropdown(
            label="Category",
            border_radius=12,
            options=[
                ft.dropdown.Option("FOOD"),
                ft.dropdown.Option("TRANSPORT"),
                ft.dropdown.Option("ACCOMMODATION"),
                ft.dropdown.Option("ACTIVITY"),
                ft.dropdown.Option("OTHER"),
            ],
            value="OTHER",
        )
        
        txt_description = ft.TextField(
            label="Remarks",
            hint_text="Dinner at restaurant, Gas, Hotel...",
            border_radius=12,
            multiline=True,
            min_lines=1,
            max_lines=2,
        )
        
        txt_amount = ft.TextField(
            label="Amount (₱)",
            hint_text="500.00",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=12,
        )
        
        # Split with checkboxes
        participant_checks = {}
        checkbox_controls = []
        
        for user_id, user_data in self.all_participants.items():
            name = user_data.get('display_name_override') or user_data.get('display_name', 'Unknown')
            is_you = user_id == config.CURRENT_USER_ID
            display_text = f"{name} (You)" if is_you else name
            
            checkbox = ft.Checkbox(
                label=display_text,
                value=user_id in config.LAST_SELECTED_PARTICIPANTS,
            )
            participant_checks[user_id] = checkbox
            checkbox_controls.append(checkbox)
        
        
        def save_expense(e):
            """Save expense OFFLINE-FIRST"""
            if not txt_description.value or not txt_amount.value:
                show_error_dialog(self.page, "Missing Fields", "Please fill remarks and amount")
                return
            
            if not dropdown_paid_by.value:
                show_error_dialog(self.page, "Missing Payer", "Please select who paid")
                return
            
            selected = [uid for uid, chk in participant_checks.items() if chk.value]
            if not selected:
                show_error_dialog(self.page, "No Participants", "Please select at least one person")
                return
            
            try:
                amount = float(txt_amount.value)
                if amount <= 0:
                    show_error_dialog(self.page, "Invalid Amount", "Amount must be greater than 0")
                    return
                
                amount_cents = int(amount * 100)
                
                # ALWAYS save offline first (no server call)
                offline_expense = {
                    'paid_by_id': dropdown_paid_by.value,
                    'amount_cents': amount_cents,
                    'category': dropdown_category.value,
                    'description': txt_description.value.strip(),
                    'participants': [
                        {'user_id': uid, 'share_amount_cents': amount_cents // len(selected)} 
                        for uid in selected
                    ]
                }
                
                config.LOCAL_EXPENSES.append(offline_expense)
                
                show_snackbar(self.page, "✓ Saved locally! Click 'Sync to Cloud' to upload.")
                config.LAST_SELECTED_PARTICIPANTS.clear()
                config.LAST_SELECTED_PARTICIPANTS.update(selected)
                
                expense_dlg.open = False
                self.page.update()
                self.refresh_callback(None)
                
            except ValueError:
                show_error_dialog(self.page, "Invalid Amount", "Please enter a valid number")
        
        
        def cancel_expense(e):
            expense_dlg.open = False
            self.page.update()
        
        def show_add_participant_nested(e):
            """Add participant from expense dialog"""
            expense_dlg.open = False
            self.page.update()
            self._show_add_participant_dialog()
        
        btn_add_participant = ft.TextButton(
            "Need to add someone? Click here",
            on_click=show_add_participant_nested,
            style=ft.ButtonStyle(color=COLORS["accent"])
        )
        
        expense_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add Expense", size=20, weight="bold"),
            content=ft.Column([
                dropdown_paid_by,
                dropdown_category,
                txt_description,
                txt_amount,
                ft.Divider(),
                ft.Text("Split with:", weight="bold", size=14),
                ft.Column(checkbox_controls, spacing=4, height=120, scroll=ft.ScrollMode.AUTO),
                ft.Divider(),
                btn_add_participant,
            ], tight=True, spacing=12, scroll=ft.ScrollMode.AUTO, height=500),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_expense),
                ft.ElevatedButton("💾 Save Offline", on_click=save_expense, 
                                 style=ft.ButtonStyle(bgcolor=COLORS["success"], color=COLORS["surface"])),
            ]
        )
        
        self.page.dialog = expense_dlg
        expense_dlg.open = True
        self.page.update()
    
    def _show_add_participant_dialog(self):
        """Add participant dialog (reusable)"""
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
    
    def _confirm_delete_expense(self, expense_id: str):
        """Confirm and delete expense"""
        def confirm(e):
            try:
                db.delete_expense(expense_id)
                self.refresh_callback(None)
                show_snackbar(self.page, "✓ Deleted")
            except Exception as ex:
                show_error_dialog(self.page, "Error", str(ex))
            dlg.open = False
            self.page.update()
        
        def cancel(e):
            dlg.open = False
            self.page.update()
        
        dlg = ft.AlertDialog(
            title=ft.Text("Delete Expense?"),
            content=ft.Text("This will recalculate all balances."),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.TextButton("Delete", on_click=confirm,
                             style=ft.ButtonStyle(color=COLORS["error"])),
            ]
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def _sync_offline_expenses(self, e):
        """Sync all offline expenses to server"""
        if not config.LOCAL_EXPENSES:
            show_snackbar(self.page, "No offline expenses to sync")
            return
        
        synced_count = 0
        failed_count = 0
        
        for local_exp in config.LOCAL_EXPENSES[:]:
            try:
                response = db.create_expense(
                    config.CURRENT_TRIP_ID,
                    local_exp['paid_by_id'],
                    local_exp['amount_cents'],
                    local_exp['category'],
                    local_exp['description']
                )
                
                if response.data and len(response.data) > 0:
                    expense_id = response.data[0]['id']
                    participants_data = local_exp.get('participants', [])
                    if participants_data:
                        # Update with expense_id
                        for p in participants_data:
                            p['expense_id'] = expense_id
                        db.add_expense_participants(participants_data)
                    
                    config.LOCAL_EXPENSES.remove(local_exp)
                    synced_count += 1
            except Exception as ex:
                print(f"Sync error: {ex}")
                failed_count += 1
        
        if synced_count > 0:
            show_snackbar(self.page, f"✓ Synced {synced_count} expense(s)!")
            self.refresh_callback(None)
        
        if failed_count > 0:
            show_error_dialog(self.page, "Partial Sync", f"{failed_count} expense(s) failed to sync")