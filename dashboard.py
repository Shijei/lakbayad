"""
Dashboard Module - View expenses, balances, and settlements with payment confirmation
"""
import flet as ft
import config
from config import COLORS
from database import db
from utils import format_currency, calculate_balances, optimize_settlements, get_user_expense_breakdown


def create_dashboard_view(page: ft.Page, all_participants: dict, show_snackbar, show_error):
    """Create dashboard view with calculations and settlement confirmations"""
    
    # UI Components
    txt_total_cost = ft.Text("Total: ₱0.00", size=24, weight="bold", color=COLORS["primary"])
    
    chk_show_offline = ft.Checkbox(
        label="Include unsynced expenses (preview)",
        value=False,
        active_color=COLORS["primary"],
    )
    
    lv_settlements = ft.ListView(expand=True, spacing=10, height=300)
    lv_balances = ft.ListView(expand=True, spacing=10, height=300)
    lv_expenses = ft.ListView(expand=True, spacing=10, height=200)
    
    def toggle_offline_preview(e):
        """Toggle offline expense preview"""
        config.SHOW_OFFLINE_PREVIEW = chk_show_offline.value
        refresh_dashboard(None)
    
    chk_show_offline.on_change = toggle_offline_preview
    
    def show_payment_dialog(from_id: str, to_id: str, amount_cents: int):
        """Show dialog to mark payment as complete with optional image"""
        from_name = all_participants.get(from_id, {}).get('display_name_override') or all_participants.get(from_id, {}).get('display_name', 'Unknown')
        to_name = all_participants.get(to_id, {}).get('display_name_override') or all_participants.get(to_id, {}).get('display_name', 'Unknown')
        amount_str = format_currency(amount_cents)
        
        # Store selected image
        selected_image = {"data": None, "name": None}
        image_preview = ft.Text("No image selected", size=12, italic=True, color=COLORS["text_secondary"])
        
        def pick_image(e):
            file_picker.pick_files(
                allowed_extensions=["png", "jpg", "jpeg"],
                allow_multiple=False
            )
        
        def on_file_result(e: ft.FilePickerResultEvent):
            if e.files and len(e.files) > 0:
                try:
                    import base64
                    file = e.files[0]
                    with open(file.path, "rb") as f:
                        image_data = f.read()
                        selected_image["data"] = base64.b64encode(image_data).decode()
                        selected_image["name"] = file.name
                    
                    image_preview.value = f"📷 {file.name}"
                    page.update()
                except Exception as ex:
                    show_error("Error", f"Failed to load image: {str(ex)}")
        
        file_picker = ft.FilePicker(on_result=on_file_result)
        page.overlay.append(file_picker)
        
        notes_field = ft.TextField(
            label="Notes (optional)",
            hint_text="Paid via GCash",
            multiline=True,
            min_lines=2,
            max_lines=3,
        )
        
        def confirm_payment(e):
            try:
                # Create settlement record in database
                response = db.create_settlement(
                    config.CURRENT_TRIP_ID,
                    from_id,
                    to_id,
                    amount_cents
                )
                
                if response.data and len(response.data) > 0:
                    settlement_id = response.data[0]['id']
                    
                    # Update with proof if provided
                    if selected_image["data"] or notes_field.value:
                        db.update_settlement_proof(
                            settlement_id,
                            proof_image=selected_image["data"],
                            notes=notes_field.value
                        )
                
                dlg.open = False
                page.overlay.remove(file_picker)
                page.update()
                
                show_snackbar(f"✓ Payment marked! {to_name} will see the confirmation.")
                
                # Refresh dashboard
                refresh_dashboard(None)
                
            except Exception as ex:
                print(f"Payment error: {ex}")
                show_error("Error", f"Failed to record payment: {str(ex)}")
        
        def cancel_dialog(e):
            dlg.open = False
            page.overlay.remove(file_picker)
            page.update()
        
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirm Payment", color=COLORS["primary"], weight="bold"),
            content=ft.Column([
                ft.Text(f"{from_name} paying {to_name}", size=16, weight="bold"),
                ft.Text(amount_str, size=24, color=COLORS["success"]),
                ft.Divider(),
                ft.Text("Optional: Upload proof of payment", size=12),
                ft.Row([
                    ft.ElevatedButton(
                        "📷 Select Image",
                        on_click=pick_image,
                        style=ft.ButtonStyle(bgcolor=COLORS["accent"], color=COLORS["surface"])
                    ),
                ]),
                image_preview,
                notes_field,
                ft.Text("This will notify the receiver", size=11, italic=True, color=COLORS["text_secondary"]),
            ], tight=True, spacing=10, scroll=ft.ScrollMode.AUTO, height=300),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_dialog),
                ft.ElevatedButton(
                    "Confirm Payment",
                    on_click=confirm_payment,
                    style=ft.ButtonStyle(bgcolor=COLORS["success"], color=COLORS["surface"])
                ),
            ],
        )
        
        page.dialog = dlg
        dlg.open = True
        page.update()
    
    def refresh_dashboard(e):
        """Refresh dashboard with calculations"""
        if not config.CURRENT_TRIP_ID:
            # Show message to select trip
            lv_settlements.controls.clear()
            lv_settlements.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.LUGGAGE, size=64, color=COLORS["text_secondary"]),
                        ft.Text("No Trip Selected", size=20, weight="bold", color=COLORS["text"]),
                        ft.Text("Please select or create a trip first", size=14, color=COLORS["text_secondary"]),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    padding=40,
                )
            )
            
            lv_balances.controls.clear()
            lv_balances.controls.append(
                ft.Text("Select a trip to view balances", italic=True, color=COLORS["text_secondary"])
            )
            
            lv_expenses.controls.clear()
            lv_expenses.controls.append(
                ft.Text("Select a trip to view expenses", italic=True, color=COLORS["text_secondary"])
            )
            
            txt_total_cost.value = "Total: ₱0.00"
            page.update()
            return
        
        try:
            # Fetch expenses
            response = db.get_trip_expenses(config.CURRENT_TRIP_ID)
            expenses_data = []
            
            for expense in response.data:
                # Keep full participant data with share amounts
                participants = expense['expense_participants']
                
                expenses_data.append({
                    'id': expense['id'],
                    'paid_by_id': expense['paid_by_id'],
                    'amount_cents': expense['amount_cents'],
                    'category': expense['category'],
                    'description': expense['description'],
                    'participants': participants,  # Full participant objects with share_amount_cents
                    'synced': True
                })
            
            # Add offline expenses if enabled
            if config.SHOW_OFFLINE_PREVIEW:
                for local_exp in config.LOCAL_EXPENSES:
                    expenses_data.append({
                        **local_exp,
                        'synced': False
                    })
            
            # Calculate total
            total_cents = sum(exp['amount_cents'] for exp in expenses_data)
            txt_total_cost.value = f"Total: {format_currency(total_cents)}"
            
            # Calculate balances (returns tuple: balances_dict, total)
            balances_dict, _ = calculate_balances(expenses_data)
            
            # Convert to old format for compatibility with update_balances_list
            balances = {}
            for user_id, balance in balances_dict.items():
                balances[user_id] = {
                    'owes': max(0, -balance),  # If negative, they owe
                    'is_owed': max(0, balance)  # If positive, they're owed
                }
            
            # Generate settlements (use raw dict)
            settlements = optimize_settlements(balances_dict)
            
            # Update settlements list
            update_settlements_list(settlements)
            
            # Update balances list
            update_balances_list(balances, expenses_data)
            
            # Update expenses list
            update_expenses_list(expenses_data)
            
            page.update()
            
        except Exception as ex:
            print(f"Dashboard error: {ex}")
            show_error("Error", f"Failed to refresh dashboard: {str(ex)}")
    
    def update_settlements_list(settlements):
        """Update settlements list with payment confirmation buttons"""
        lv_settlements.controls.clear()
        
        if not settlements:
            lv_settlements.controls.append(
                ft.Text("✓ All settled up!", size=16, color=COLORS["success"], weight="bold")
            )
        else:
            for settlement in settlements:
                from_id = settlement['from_id']
                to_id = settlement['to_id']
                amount = settlement['amount_cents']
                
                from_name = all_participants.get(from_id, {}).get('display_name_override') or all_participants.get(from_id, {}).get('display_name', 'Unknown')
                to_name = all_participants.get(to_id, {}).get('display_name_override') or all_participants.get(to_id, {}).get('display_name', 'Unknown')
                amount_str = format_currency(amount)
                
                # Check if current user is involved
                is_payer = from_id == config.CURRENT_USER_ID
                is_receiver = to_id == config.CURRENT_USER_ID
                
                # Highlight if current user is involved
                bg_color = COLORS["secondary"] if (is_payer or is_receiver) else COLORS["surface"]
                
                # Build trailing button for payer
                trailing = None
                if is_payer:
                    def make_payment_handler(f_id, t_id, amt):
                        def handler(e):
                            show_payment_dialog(f_id, t_id, amt)
                        return handler
                    
                    trailing = ft.IconButton(
                        icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                        icon_color=COLORS["success"],
                        icon_size=24,
                        tooltip="Mark as paid",
                        on_click=make_payment_handler(from_id, to_id, amount)
                    )
                
                lv_settlements.controls.append(
                    ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon(ft.Icons.ARROW_FORWARD, color=COLORS["success"]),
                            title=ft.Text(f"{from_name} → {to_name}", weight="bold"),
                            subtitle=ft.Text(amount_str, size=18, color=COLORS["success"]),
                            trailing=trailing,
                        ),
                        bgcolor=bg_color,
                        border_radius=8,
                        padding=5,
                    )
                )
        
        page.update()
    
    def update_balances_list(balances, expenses_data):
        """Update balances list with breakdown"""
        lv_balances.controls.clear()
        
        if not balances:
            lv_balances.controls.append(
                ft.Text("No balances yet", italic=True, color=COLORS["text_secondary"])
            )
        else:
            for user_id, balance in balances.items():
                is_current_user = user_id == config.CURRENT_USER_ID
                user_name = all_participants.get(user_id, {}).get('display_name_override') or all_participants.get(user_id, {}).get('display_name', 'Unknown')
                
                balance_cents = balance['owes'] - balance['is_owed']
                
                if balance_cents > 0:
                    # Owes money
                    status = f"Owes {format_currency(balance_cents)}"
                    icon = ft.Icons.ARROW_UPWARD
                    icon_color = COLORS["error"]
                elif balance_cents < 0:
                    # Is owed money
                    status = f"Is owed {format_currency(abs(balance_cents))}"
                    icon = ft.Icons.ARROW_DOWNWARD
                    icon_color = COLORS["success"]
                else:
                    # Settled
                    status = "Settled ✓"
                    icon = ft.Icons.CHECK_CIRCLE
                    icon_color = COLORS["success"]
                
                # Get expense breakdown
                breakdown_content = None
                if is_current_user:
                    breakdown = get_user_expense_breakdown(user_id, expenses_data, all_participants)
                    
                    if breakdown['paid'] or breakdown['owes']:
                        breakdown_items = []
                        
                        if breakdown['paid']:
                            breakdown_items.append(ft.Text("You paid for:", weight="bold", size=12))
                            for item in breakdown['paid'][:5]:
                                breakdown_items.append(ft.Text(f"• {item}", size=11))
                            if len(breakdown['paid']) > 5:
                                breakdown_items.append(ft.Text(f"... and {len(breakdown['paid']) - 5} more", size=11, italic=True))
                        
                        if breakdown['owes']:
                            breakdown_items.append(ft.Text("You owe for:", weight="bold", size=12))
                            for item in breakdown['owes'][:5]:
                                breakdown_items.append(ft.Text(f"• {item}", size=11))
                            if len(breakdown['owes']) > 5:
                                breakdown_items.append(ft.Text(f"... and {len(breakdown['owes']) - 5} more", size=11, italic=True))
                        
                        breakdown_content = ft.Container(
                            content=ft.Column(breakdown_items, spacing=5),
                            padding=10,
                            bgcolor=COLORS["bg"],
                            border_radius=8,
                            visible=False,
                        )
                
                # Create expandable tile
                container_content = ft.Column([
                    ft.ListTile(
                        title=ft.Row([
                            ft.Text(user_name, weight="bold"),
                            ft.Text("(You)", size=12, color=COLORS["primary"], italic=True) if is_current_user else ft.Container()
                        ], spacing=10),
                        subtitle=ft.Text(status, size=14),
                        leading=ft.Icon(icon, color=icon_color),
                        trailing=ft.IconButton(
                            icon=ft.Icons.HELP_OUTLINE,
                            tooltip="Click to show breakdown",
                            icon_color=COLORS["accent"],
                            icon_size=20,
                        ) if is_current_user and breakdown_content else None,
                    ),
                ])
                
                if is_current_user and breakdown_content:
                    breakdown_content.visible = False
                    container_content.controls.append(breakdown_content)
                
                def make_toggle_handler(bd_content):
                    def handler(e):
                        bd_content.visible = not bd_content.visible
                        page.update()
                    return handler
                
                container = ft.Container(
                    content=container_content,
                    bgcolor=COLORS["secondary"] if is_current_user else COLORS["surface"],
                    border_radius=8,
                    padding=5,
                )
                
                if is_current_user and breakdown_content:
                    container.on_click = make_toggle_handler(breakdown_content)
                    container.ink = True
                
                lv_balances.controls.append(container)
        
        page.update()
    
    def update_expenses_list(expenses_data):
        """Update expenses list with delete buttons"""
        lv_expenses.controls.clear()
        
        if not expenses_data:
            lv_expenses.controls.append(
                ft.Text("No expenses yet", italic=True, color=COLORS["text_secondary"])
            )
        else:
            synced_expenses = [e for e in expenses_data if e.get('synced', True)]
            
            for expense in synced_expenses:
                paid_by_name = all_participants.get(expense['paid_by_id'], {}).get('display_name_override') or all_participants.get(expense['paid_by_id'], {}).get('display_name', 'Unknown')
                amount_str = format_currency(expense['amount_cents'])
                
                # Check if current user is creator
                is_creator = expense['paid_by_id'] == config.CURRENT_USER_ID
                
                def make_delete_handler(exp_id):
                    def handler(e):
                        def confirm_delete(e):
                            try:
                                db.delete_expense(exp_id)
                                refresh_dashboard(None)
                                show_snackbar("✓ Expense deleted")
                            except Exception as ex:
                                show_error("Error", f"Failed to delete: {str(ex)}")
                            confirm_dlg.open = False
                            page.update()
                        
                        def cancel_delete(e):
                            confirm_dlg.open = False
                            page.update()
                        
                        confirm_dlg = ft.AlertDialog(
                            modal=True,
                            title=ft.Text("Delete Expense?", color=COLORS["error"]),
                            content=ft.Text("This will permanently delete this expense and recalculate balances."),
                            actions=[
                                ft.TextButton("Cancel", on_click=cancel_delete),
                                ft.TextButton("Delete", on_click=confirm_delete),
                            ],
                        )
                        page.dialog = confirm_dlg
                        confirm_dlg.open = True
                        page.update()
                    return handler
                
                lv_expenses.controls.append(
                    ft.Container(
                        content=ft.ListTile(
                            title=ft.Text(expense['description'], size=14),
                            subtitle=ft.Text(f"{paid_by_name} • {amount_str}", size=12),
                            leading=ft.Icon(ft.Icons.RECEIPT, color=COLORS["accent"], size=20),
                            trailing=ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=COLORS["error"],
                                icon_size=18,
                                tooltip="Delete expense",
                                on_click=make_delete_handler(expense['id'])
                            ) if is_creator and expense.get('id') else None,
                        ),
                        bgcolor=COLORS["surface"],
                        border_radius=8,
                        padding=2,
                    )
                )
        
        page.update()
    
    btn_refresh = ft.Button(
        "🔄 Refresh",
        on_click=refresh_dashboard,
        style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"]),
        width=200,
    )
    
    # Main view
    view_dashboard = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Text("Dashboard", size=24, weight="bold", color=COLORS["primary"]),
                    btn_refresh,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=20,
            ),
            
            # Total cost and checkbox
            ft.Container(
                content=ft.Column([
                    txt_total_cost,
                    chk_show_offline,
                ]),
                padding=20,
                bgcolor=COLORS["surface"],
                border_radius=10,
                margin=10,
            ),
            
            # Settlements
            ft.Container(
                content=ft.Column([
                    ft.Text("💰 Settlements", weight="bold", size=18, color=COLORS["text"]),
                    ft.Text("Optimized payments (fewest transactions)", size=12, italic=True, color=COLORS["text_secondary"]),
                    lv_settlements,
                ]),
                padding=20,
                bgcolor=COLORS["surface"],
                border_radius=10,
                margin=10,
            ),
            
            # Balances
            ft.Container(
                content=ft.Column([
                    ft.Text("📊 Balances", weight="bold", size=18, color=COLORS["text"]),
                    ft.Text("Click '?' on your name to see breakdown", size=12, italic=True, color=COLORS["text_secondary"]),
                    lv_balances,
                ]),
                padding=20,
                bgcolor=COLORS["surface"],
                border_radius=10,
                margin=10,
            ),
            
            # Expenses
            ft.Container(
                content=ft.Column([
                    ft.Text("📝 All Expenses", weight="bold", size=18, color=COLORS["text"]),
                    ft.Text("Creators can delete their expenses", size=12, italic=True, color=COLORS["text_secondary"]),
                    lv_expenses,
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
    
    return view_dashboard, refresh_dashboard