"""
Expenses Module - Add expenses with selective participant splitting
"""
import flet as ft
import config
from config import COLORS
from database import db
from utils import format_currency
from datetime import datetime


def create_expenses_view(page: ft.Page, all_participants: dict, show_snackbar, show_error):
    """Create expense entry view with selective splitting"""
    
    # UI Components
    dd_paid_by = ft.Dropdown(
        label="Who Paid?",
        width=300,
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
    )
    
    txt_amount = ft.TextField(
        label="Amount (₱)",
        hint_text="100.00",
        keyboard_type=ft.KeyboardType.NUMBER,
        width=300,
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
    )
    
    dd_category = ft.Dropdown(
        label="Category",
        width=300,
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
        options=[
            ft.dropdown.Option("Food"),
            ft.dropdown.Option("Transport"),
            ft.dropdown.Option("Accommodation"),
            ft.dropdown.Option("Activities"),
            ft.dropdown.Option("Shopping"),
            ft.dropdown.Option("Other"),
        ],
        value="Food",
    )
    
    txt_description = ft.TextField(
        label="Description",
        hint_text="Lunch at restaurant",
        width=300,
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
        multiline=True,
        min_lines=2,
        max_lines=3,
    )
    
    # Participant checkboxes for selective splitting
    participant_checkboxes = ft.Column(spacing=5)
    
    def update_participant_checkboxes():
        """Update checkbox list when participants change"""
        participant_checkboxes.controls.clear()
        
        if not all_participants:
            participant_checkboxes.controls.append(
                ft.Text("No participants yet. Add some in the Participants tab!", 
                       italic=True, color=COLORS["text_secondary"])
            )
        else:
            participant_checkboxes.controls.append(
                ft.Text("Split among:", weight="bold", color=COLORS["text"])
            )
            
            for user_id, user_data in all_participants.items():
                # Check if this user was selected last time (remembered selection)
                is_checked = user_id in config.LAST_SELECTED_PARTICIPANTS
                
                # New participants default to checked
                if not config.LAST_SELECTED_PARTICIPANTS:
                    is_checked = True
                
                checkbox = ft.Checkbox(
                    label=user_data['display_name'],
                    value=is_checked,
                    data=user_id,  # Store user_id in data
                    active_color=COLORS["primary"],
                )
                participant_checkboxes.controls.append(checkbox)
        
        page.update()
    
    def update_paid_by_dropdown():
        """Update dropdown when participants change"""
        dd_paid_by.options = [
            ft.dropdown.Option(key=uid, text=udata['display_name'])
            for uid, udata in all_participants.items()
        ]
        
        # Auto-select current user if exists
        if config.CURRENT_USER_ID in all_participants:
            dd_paid_by.value = config.CURRENT_USER_ID
        
        page.update()
    
    def get_selected_participants():
        """Get list of selected participant IDs"""
        selected = []
        for control in participant_checkboxes.controls:
            if isinstance(control, ft.Checkbox) and control.value:
                selected.append(control.data)
        return selected
    
    def save_offline(e):
        """Save expense offline"""
        if not config.CURRENT_TRIP_ID:
            show_error("No Trip Selected", "Please select or create a trip first")
            return
        
        if not dd_paid_by.value:
            show_error("Missing Info", "Please select who paid")
            return
        
        if not txt_amount.value:
            show_error("Missing Amount", "Please enter an amount")
            return
        
        try:
            amount_pesos = float(txt_amount.value)
            if amount_pesos <= 0:
                show_error("Invalid Amount", "Amount must be greater than 0")
                return
        except ValueError:
            show_error("Invalid Amount", "Please enter a valid number")
            return
        
        selected_participants = get_selected_participants()
        if not selected_participants:
            show_error("No Participants", "Please select at least one person to split with")
            return
        
        # Remember selection for next time
        config.LAST_SELECTED_PARTICIPANTS = set(selected_participants)
        
        # Convert to centavos
        amount_cents = int(amount_pesos * 100)
        
        # Calculate split (simple division)
        num_participants = len(selected_participants)
        share_per_person = amount_cents // num_participants
        
        # Store offline
        expense_data = {
            'paid_by_id': dd_paid_by.value,
            'amount_cents': amount_cents,
            'category': dd_category.value,
            'description': txt_description.value or "Expense",
            'participants': [
                {'user_id': uid, 'share_amount_cents': share_per_person}
                for uid in selected_participants
            ]
        }
        
        config.LOCAL_EXPENSES.append(expense_data)
        
        # Update the unsynced view immediately
        update_unsynced_view()
        
        # Clear form
        txt_amount.value = ""
        txt_description.value = ""
        
        show_snackbar(f"✓ Expense saved offline ({len(config.LOCAL_EXPENSES)} unsynced)")
        
        # Keep checkboxes as they were (remembered)
        page.update()
    
    def sync_to_cloud(e):
        """Sync offline expenses to cloud"""
        if not config.LOCAL_EXPENSES:
            show_snackbar("Nothing to sync")
            return
        
        if not config.CURRENT_TRIP_ID:
            show_error("No Trip", "Please select a trip first")
            return
        
        btn_sync.disabled = True
        btn_sync.text = "Syncing..."
        page.update()
        
        try:
            # Validate all participants exist
            participant_ids_needed = set()
            for item in config.LOCAL_EXPENSES:
                participant_ids_needed.add(item['paid_by_id'])
                for p in item['participants']:
                    participant_ids_needed.add(p['user_id'])
            
            for uid in participant_ids_needed:
                if uid not in all_participants:
                    show_error("Error", f"User not found. Please add all participants first.")
                    btn_sync.disabled = False
                    btn_sync.text = "☁️ Sync to Cloud"
                    page.update()
                    return
            
            # Sync each expense
            for item in config.LOCAL_EXPENSES:
                expense_response = db.create_expense(
                    config.CURRENT_TRIP_ID,
                    item['paid_by_id'],
                    item['amount_cents'],
                    item['category'],
                    item['description']
                )
                
                expense_id = expense_response.data[0]['id']
                
                participant_data = [
                    {
                        "expense_id": expense_id,
                        "user_id": p['user_id'],
                        "share_amount_cents": p['share_amount_cents']
                    }
                    for p in item['participants']
                ]
                
                db.add_expense_participants(participant_data)
            
            count = len(config.LOCAL_EXPENSES)
            config.LOCAL_EXPENSES.clear()
            show_snackbar(f"✓ {count} expenses synced successfully!")
            
        except Exception as ex:
            print(f"SYNC FAILED: {ex}")
            show_error("Sync Failed", str(ex))
        
        btn_sync.disabled = False
        btn_sync.text = "☁️ Sync to Cloud"
        page.update()
    
    btn_save_offline = ft.Button(
        "💾 Save Offline",
        on_click=save_offline,
        style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"]),
        width=300,
    )
    
    btn_sync = ft.Button(
        "☁️ Sync to Cloud",
        on_click=sync_to_cloud,
        style=ft.ButtonStyle(bgcolor=COLORS["success"], color=COLORS["surface"]),
        width=300,
    )
    
    # Unsynced expenses list
    lv_unsynced = ft.ListView(expand=True, spacing=5, height=200)
    
    def update_unsynced_view():
        """Update unsynced expenses list"""
        lv_unsynced.controls.clear()
        
        if not config.LOCAL_EXPENSES:
            lv_unsynced.controls.append(
                ft.Text("No unsynced expenses", italic=True, color=COLORS["text_secondary"])
            )
        else:
            for idx, expense in enumerate(config.LOCAL_EXPENSES):
                paid_by_name = all_participants.get(expense['paid_by_id'], {}).get('display_name', 'Unknown')
                amount_str = format_currency(expense['amount_cents'])
                
                # Check if current user is the one who paid (creator)
                is_creator = expense['paid_by_id'] == config.CURRENT_USER_ID
                
                def make_delete_handler(index):
                    def handler(e):
                        # Confirm deletion
                        def confirm_delete(e):
                            config.LOCAL_EXPENSES.pop(index)
                            update_unsynced_view()
                            show_snackbar("✓ Expense deleted")
                            confirm_dlg.open = False
                            page.update()
                        
                        def cancel_delete(e):
                            confirm_dlg.open = False
                            page.update()
                        
                        confirm_dlg = ft.AlertDialog(
                            modal=True,
                            title=ft.Text("Delete Expense?", color=COLORS["error"]),
                            content=ft.Text("This will remove this unsynced expense."),
                            actions=[
                                ft.TextButton("Cancel", on_click=cancel_delete),
                                ft.TextButton("Delete", on_click=confirm_delete),
                            ],
                        )
                        page.dialog = confirm_dlg
                        confirm_dlg.open = True
                        page.update()
                    return handler
                
                lv_unsynced.controls.append(
                    ft.Container(
                        content=ft.ListTile(
                            title=ft.Text(expense['description'], weight="bold"),
                            subtitle=ft.Text(f"{paid_by_name} paid {amount_str} • {expense['category']}"),
                            leading=ft.Icon(ft.Icons.RECEIPT, color=COLORS["warning"]),
                            trailing=ft.IconButton(
                                icon=ft.Icons.DELETE,
                                icon_color=COLORS["error"],
                                tooltip="Delete expense",
                                on_click=make_delete_handler(idx)
                            ) if is_creator else None,
                        ),
                        bgcolor=COLORS["surface"],
                        border_radius=8,
                        padding=5,
                    )
                )
        
        page.update()
    
    # Main view
    view_expenses = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text("Add Expense", size=24, weight="bold", color=COLORS["primary"]),
                padding=20,
            ),
            
            # Form
            ft.Container(
                content=ft.Column([
                    ft.Text("Expense Details", weight="bold", size=18, color=COLORS["text"]),
                    dd_paid_by,
                    txt_amount,
                    dd_category,
                    txt_description,
                ], spacing=15),
                padding=20,
                bgcolor=COLORS["surface"],
                border_radius=10,
                margin=10,
            ),
            
            # Participant selection
            ft.Container(
                content=ft.Column([
                    participant_checkboxes,
                ], scroll="auto"),
                padding=20,
                bgcolor=COLORS["surface"],
                border_radius=10,
                margin=10,
                height=200,
            ),
            
            # Buttons
            ft.Container(
                content=ft.Column([
                    btn_save_offline,
                    ft.Text(
                        f"Unsynced: {len(config.LOCAL_EXPENSES)}",
                        size=12,
                        color=COLORS["warning"],
                        weight="bold"
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                padding=10,
            ),
            
            # Unsynced list
            ft.Container(
                content=ft.Column([
                    ft.Text("Unsynced Expenses", weight="bold", size=18, color=COLORS["text"]),
                    lv_unsynced,
                    btn_sync,
                ]),
                padding=20,
                bgcolor=COLORS["surface"],
                border_radius=10,
                margin=10,
            ),
            
        ], scroll="auto"),
        padding=0,
    )
    
    return view_expenses, update_participant_checkboxes, update_paid_by_dropdown, update_unsynced_view