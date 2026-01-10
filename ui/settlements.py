"""
Settlements Module - Settlement management and payment tracking
"""
import base64
import flet as ft
import config
from config import COLORS
from database import db
from utils import format_currency
from .helpers import show_snackbar, show_error_dialog, create_card_style


class SettlementsComponent:
    """Component for managing settlements and payments"""
    
    def __init__(self):
        self.lv_settlements = ft.ListView(spacing=8, height=250)
        self.lv_balances = ft.ListView(spacing=8, height=200)
        self.pending_payments_section = ft.Container(visible=False)
        self.payment_history_section = ft.Container(visible=False)
        self.lv_pending = ft.ListView(spacing=8, height=200)
        self.lv_history = ft.ListView(spacing=8, height=200)
    
    def create_settlements_section(self):
        """Create settlements section UI"""
        return ft.Container(
            content=ft.Column([
                ft.Text("💸 Settlements", size=18, weight="bold"),
                ft.Text("Optimized payments (fewest transactions)", 
                       size=12, italic=True, color=COLORS["text_secondary"]),
                ft.Container(height=12),
                self.lv_settlements,
            ]),
            **create_card_style()
        )
    
    def create_balances_section(self):
        """Create balances section UI"""
        return ft.Container(
            content=ft.Column([
                ft.Text("📊 Balances", size=18, weight="bold"),
                ft.Container(height=12),
                self.lv_balances,
            ]),
            **create_card_style()
        )
    
    def create_pending_section(self):
        """Create pending payments section UI"""
        self.pending_payments_section = ft.Container(
            content=ft.Column([
                ft.Text("💰 Payment Confirmations", size=18, weight="bold"),
                ft.Text("Payments waiting for your confirmation", 
                       size=12, italic=True, color=COLORS["text_secondary"]),
                ft.Container(height=12),
                self.lv_pending,
            ]),
            **create_card_style(),
            visible=False
        )
        return self.pending_payments_section
    
    def create_history_section(self):
        """Create payment history section UI"""
        self.payment_history_section = ft.Container(
            content=ft.Column([
                ft.Text("📜 Payment History", size=18, weight="bold"),
                ft.Text("Recently confirmed payments", 
                       size=12, italic=True, color=COLORS["text_secondary"]),
                ft.Container(height=12),
                self.lv_history,
            ]),
            **create_card_style(),
            visible=False
        )
        return self.payment_history_section
    
    def update_settlements(self, settlements: list, all_participants: dict,
                          pending_tracker: dict, status_dict: dict):
        """
        Update settlements list
        
        Args:
            settlements: List of settlement dicts
            all_participants: Dict of participants
            pending_tracker: Dict tracking pending settlements
            status_dict: Dict tracking settlement statuses
        """
        self.page = getattr(self, 'page', None)
        self.all_participants = all_participants
        self.pending_tracker = pending_tracker
        self.status_dict = status_dict
        
        self.lv_settlements.controls.clear()
        
        if not settlements:
            self.lv_settlements.controls.append(
                ft.Container(
                    content=ft.Text("✓ All settled up!", color=COLORS["success"], 
                                   weight="bold", size=16),
                    padding=20,
                )
            )
        else:
            for settlement in settlements:
                from_id = settlement['from_id']
                to_id = settlement['to_id']
                amount = settlement['amount_cents']
                
                from_name = all_participants.get(from_id, {}).get('display_name_override') or \
                            all_participants.get(from_id, {}).get('display_name', 'Unknown')
                to_name = all_participants.get(to_id, {}).get('display_name_override') or \
                          all_participants.get(to_id, {}).get('display_name', 'Unknown')
                amount_str = format_currency(amount)
                
                is_involved = from_id == config.CURRENT_USER_ID or to_id == config.CURRENT_USER_ID
                is_payer = from_id == config.CURRENT_USER_ID
                
                # Check settlement status
                settlement_key = f"{from_id}_{to_id}_{amount}"
                is_pending = settlement_key in pending_tracker
                
                # Check if confirmed AND validate amount matches
                status_key = f"{from_id}_{to_id}"
                status_record = status_dict.get(status_key, None)
                status = None
                
                # DEBUG: Log what we're checking
                # print(f"[DEBUG] Checking settlement: {from_name} → {to_name}")
                # print(f"[DEBUG] Current amount: ₱{amount/100:.2f} ({amount} cents)")
                # print(f"[DEBUG] Status key: {status_key}")
                # print(f"[DEBUG] Status record: {status_record}")
                
                # Handle both old format (string) and new format (dict)
                if status_record:
                    if isinstance(status_record, dict):
                        # New format: {'status': 'pending', 'amount_cents': 50000, 'id': '...'}
                        stored_amount = status_record.get('amount_cents', 0)
                        stored_status = status_record.get('status')
                        current_amount = amount
                        
                        if stored_amount == current_amount:
                            # Amount matches - use stored status
                            status = stored_status
                        else:
                            # Amount changed!
                            settlement_id = status_record.get('id')
                            
                            if stored_status == 'confirmed':
                                # VOID the confirmed payment (keep in history)
                                print(f"[SETTLEMENT] Amount changed: ₱{stored_amount/100:.2f} → ₱{current_amount/100:.2f}")
                                print(f"[SETTLEMENT] Voiding confirmed settlement: {settlement_id}")
                                
                                try:
                                    from database import db
                                    # Update status to 'voided' instead of deleting
                                    db._request("PATCH", "settlements", params={
                                        "id": f"eq.{settlement_id}"
                                    }, json_data={
                                        "status": "voided",
                                        "void_reason": "Balance changed - New expenses added"
                                    })
                                    print(f"[SETTLEMENT] Successfully voided settlement")
                                    
                                    # Send notifications
                                    # To payer
                                    try:
                                        db.create_notification(
                                            user_id=from_id,
                                            trip_id=config.CURRENT_TRIP_ID,
                                            message=f"Your ₱{stored_amount/100:.2f} payment was voided. Balance changed to ₱{current_amount/100:.2f}. Please re-send payment confirmation.",
                                            notification_type="settlement_voided"
                                        )
                                    except:
                                        pass
                                    
                                    # To receiver
                                    try:
                                        from_name = all_participants.get(from_id, {}).get('display_name', 'Someone')
                                        db.create_notification(
                                            user_id=to_id,
                                            trip_id=config.CURRENT_TRIP_ID,
                                            message=f"{from_name}'s ₱{stored_amount/100:.2f} payment was voided due to balance change. Payer will resend new confirmation.",
                                            notification_type="settlement_voided"
                                        )
                                    except:
                                        pass
                                        
                                except Exception as void_ex:
                                    print(f"[SETTLEMENT] Failed to void: {void_ex}")
                            
                            elif stored_status == 'pending' or stored_status == 'rejected':
                                # Auto-cancel pending/rejected (delete entirely)
                                print(f"[SETTLEMENT] Amount changed: ₱{stored_amount/100:.2f} → ₱{current_amount/100:.2f}")
                                print(f"[SETTLEMENT] Auto-cancelling {stored_status.upper()} settlement: {settlement_id}")
                                
                                try:
                                    from database import db
                                    db._request("DELETE", f"settlements?id=eq.{settlement_id}")
                                    print(f"[SETTLEMENT] Successfully cancelled settlement")
                                except Exception as cancel_ex:
                                    print(f"[SETTLEMENT] Failed to cancel: {cancel_ex}")
                            
                            # Either way, treat current settlement as new (no status)
                            status = None
                    else:
                        # Old format: status_record is just a string like 'confirmed'
                        # Can't validate amount, so just use the status
                        status = status_record
                        print(f"[SETTLEMENT] Warning: Using old status format (string), can't validate amount")
                
                # Create appropriate button/icon based on status
                trailing = None
                
                if is_payer and status != "confirmed":
                    if not is_pending:
                        # Default: Show payment icon button (no text to save space)
                        def make_handler(f_id, t_id, amt):
                            def handler(e):
                                self._show_mark_paid_dialog(f_id, t_id, amt)
                            return handler
                        
                        trailing = ft.IconButton(
                            icon=ft.Icons.PAYMENT,
                            icon_color=COLORS["surface"],
                            bgcolor=COLORS["success"],
                            on_click=make_handler(from_id, to_id, amount),
                            tooltip="Mark as Paid",  # Tooltip shows on hover
                            icon_size=24,
                        )
                    else:
                        # Pending: Show hourglass icon
                        trailing = ft.Row([
                            ft.Icon(ft.Icons.HOURGLASS_EMPTY, color=COLORS["warning"], size=20),
                            ft.Text("Pending", size=12, color=COLORS["warning"], weight="bold")
                        ], tight=True, spacing=4)
                
                # Different display based on confirmed status
                if status == "confirmed":
                    # Paid & Settled - Show green badge
                    title_content = ft.Row([
                        ft.Text(
                            f"{from_name} → {to_name}", 
                            weight="bold", 
                            size=13,  # Smaller font
                            overflow=ft.TextOverflow.ELLIPSIS,  # Truncate if too long
                        ),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.CHECK_CIRCLE, color=COLORS["success"], size=12),
                                ft.Text("Paid", size=10, color=COLORS["success"], weight="bold")  # Shorter text
                            ], tight=True, spacing=2),
                            bgcolor=ft.colors.GREEN_50,
                            padding=4,
                            border_radius=6,
                            margin=ft.margin.only(left=4)
                        )
                    ], tight=True)
                    subtitle_color = COLORS["text_secondary"]
                    bg_color = ft.colors.GREEN_50
                    icon_type = ft.Icons.CHECK_CIRCLE
                else:
                    title_content = ft.Text(
                        f"{from_name} → {to_name}", 
                        weight="bold", 
                        size=13,  # Smaller font
                        overflow=ft.TextOverflow.ELLIPSIS,  # Truncate if too long
                        max_lines=1,
                    )
                    subtitle_color = COLORS["success"]
                    bg_color = COLORS["secondary"] if is_involved else COLORS["surface"]
                    icon_type = ft.Icons.ARROW_FORWARD
                
                self.lv_settlements.controls.append(
                    ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon(icon_type, color=COLORS["success"], size=24),
                            title=title_content,
                            subtitle=ft.Text(
                                amount_str, 
                                size=16,  # Reduced from 18
                                color=subtitle_color, 
                                weight="w600",
                                overflow=ft.TextOverflow.ELLIPSIS,  # Prevent overflow
                                max_lines=1,  # Keep on one line
                            ),
                            trailing=trailing,
                        ),
                        bgcolor=bg_color,
                        border_radius=12,
                        padding=8,
                        margin=ft.margin.only(bottom=8),
                    )
                )
    
    def update_balances(self, balances: dict, all_participants: dict):
        """Update balances list"""
        self.lv_balances.controls.clear()
        
        for user_id, balance_data in balances.items():
            is_you = user_id == config.CURRENT_USER_ID
            name = all_participants.get(user_id, {}).get('display_name_override') or \
                   all_participants.get(user_id, {}).get('display_name', 'Unknown')
            
            display_name = f"{name} (You)" if is_you else name
            
            owes = balance_data['owes']
            is_owed = balance_data['is_owed']
            
            if owes > 0:
                subtitle = f"Owes {format_currency(owes)}"
                color = COLORS["error"]
            elif is_owed > 0:
                subtitle = f"Is owed {format_currency(is_owed)}"
                color = COLORS["success"]
            else:
                subtitle = "Settled up ✓"
                color = COLORS["text_secondary"]
            
            self.lv_balances.controls.append(
                ft.Container(
                    content=ft.ListTile(
                        title=ft.Text(display_name, size=14, weight="w500"),
                        subtitle=ft.Text(subtitle, size=13, color=color, weight="bold"),
                    ),
                    bgcolor=COLORS["secondary"] if is_you else COLORS["surface"],
                    border_radius=12,
                    padding=4,
                    margin=ft.margin.only(bottom=4),
                )
            )
    
    def update_pending_payments(self, pending_payments: list, all_participants: dict):
        """Update pending payments list"""
        self.lv_pending.controls.clear()
        
        if not pending_payments:
            self.pending_payments_section.visible = False
        else:
            self.pending_payments_section.visible = True
            
            for payment in pending_payments:
                payer_id = payment['payer_id']
                amount_cents = payment['amount_cents']
                notes = payment.get('notes')
                has_image = payment.get('proof_image_base64') is not None
                
                payer_name = all_participants.get(payer_id, {}).get('display_name_override') or \
                             all_participants.get(payer_id, {}).get('display_name', 'Unknown')
                amount_str = format_currency(amount_cents)
                
                def make_confirm_handler(settlement_id, p_name, amt_str):
                    def handler(e):
                        self._confirm_payment_received(settlement_id, p_name, amt_str)
                    return handler
                
                def make_reject_handler(settlement_id, p_name, amt_str):
                    def handler(e):
                        self._reject_payment(settlement_id, p_name, amt_str)
                    return handler
                
                def make_view_handler(img_base64):
                    def handler(e):
                        self._show_image_proof(img_base64)
                    return handler
                
                actions = [
                    ft.ElevatedButton(
                        "All Goods ✓",
                        on_click=make_confirm_handler(payment['id'], payer_name, amount_str),
                        style=ft.ButtonStyle(bgcolor=COLORS["success"], color=COLORS["surface"]),
                        height=36,
                    ),
                    ft.ElevatedButton(
                        "Not Good ✗",
                        on_click=make_reject_handler(payment['id'], payer_name, amount_str),
                        style=ft.ButtonStyle(bgcolor=COLORS["error"], color=COLORS["surface"]),
                        height=36,
                    ),
                ]
                
                if has_image:
                    actions.insert(0, ft.IconButton(
                        icon=ft.Icons.IMAGE,
                        tooltip="View proof",
                        icon_size=20,
                        on_click=make_view_handler(payment['proof_image_base64'])
                    ))
                
                self.lv_pending.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.ListTile(
                                title=ft.Text(f"{payer_name} paid you", size=14, weight="bold"),
                                subtitle=ft.Text(f"{amount_str}{f' • {notes}' if notes else ''}", size=13),
                            ),
                            ft.Row(actions, spacing=8, wrap=True),
                        ], spacing=8),
                        bgcolor=COLORS["secondary"],
                        border_radius=12,
                        padding=12,
                        margin=ft.margin.only(bottom=8),
                    )
                )
    
    def update_payment_history(self, payment_history: list):
        """Update payment history list"""
        self.lv_history.controls.clear()
        
        if not payment_history:
            self.payment_history_section.visible = False
        else:
            self.payment_history_section.visible = True
            
            for payment in payment_history[:10]:  # Show last 10
                # Extract names from nested objects or fallback to IDs
                payer_data = payment.get('payer')
                receiver_data = payment.get('receiver')
                
                if payer_data and isinstance(payer_data, dict):
                    payer_name = payer_data.get('display_name', 'Unknown')
                else:
                    # Fallback: try to get from all_participants using payer_id
                    payer_id = payment.get('payer_id')
                    payer_name = self.all_participants.get(payer_id, {}).get('display_name', 'Unknown')
                
                if receiver_data and isinstance(receiver_data, dict):
                    receiver_name = receiver_data.get('display_name', 'Unknown')
                else:
                    # Fallback: try to get from all_participants using receiver_id
                    receiver_id = payment.get('receiver_id')
                    receiver_name = self.all_participants.get(receiver_id, {}).get('display_name', 'Unknown')
                
                amount_str = format_currency(payment['amount_cents'])
                status = payment.get('status', 'confirmed')
                date = payment.get('confirmed_at', '')[:10] if payment.get('confirmed_at') else ''
                
                # Check if voided
                is_voided = status == 'voided'
                void_reason = payment.get('void_reason', 'Balance changed')
                
                if is_voided:
                    # Voided payment - strikethrough with warning icon
                    leading_icon = ft.Icon(ft.Icons.WARNING, color=COLORS["warning"], size=20)
                    title_text = ft.Text(
                        f"{payer_name} → {receiver_name}",
                        size=13,
                        color=COLORS["text_secondary"],
                        style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)  # Strikethrough
                    )
                    subtitle_text = ft.Text(
                        f"{amount_str} • {date}\nVOIDED: {void_reason}",
                        size=11,
                        color=COLORS["warning"]
                    )
                    bg_color = ft.colors.ORANGE_50
                else:
                    # Confirmed payment - normal display
                    leading_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, color=COLORS["success"], size=20)
                    title_text = ft.Text(f"{payer_name} → {receiver_name}", size=13)
                    subtitle_text = ft.Text(
                        f"{amount_str} • {date}\nConfirmed",
                        size=11,
                        color=COLORS["text_secondary"]
                    )
                    bg_color = COLORS["surface"]
                
                self.lv_history.controls.append(
                    ft.Container(
                        content=ft.ListTile(
                            leading=leading_icon,
                            title=title_text,
                            subtitle=subtitle_text,
                        ),
                        bgcolor=bg_color,
                        border_radius=12,
                        padding=4,
                        margin=ft.margin.only(bottom=4),
                    )
                )
    
    def _show_mark_paid_dialog(self, from_id: str, to_id: str, amount_cents: int):
        """Show mark as paid dialog"""
        to_name = self.all_participants.get(to_id, {}).get('display_name_override') or \
                  self.all_participants.get(to_id, {}).get('display_name', 'Unknown')
        amount_str = format_currency(amount_cents)
        
        selected_image = {"data": None, "name": None}
        image_preview = ft.Text("No image selected", size=12, italic=True, color=COLORS["text_secondary"])
        
        def pick_image(e):
            file_picker.pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE
            )
        
        def on_file_result(e: ft.FilePickerResultEvent):
            if e.files and len(e.files) > 0:
                try:
                    file = e.files[0]
                    # Desktop: has path attribute
                    if hasattr(file, 'path') and file.path:
                        with open(file.path, "rb") as f:
                            image_data = f.read()
                            selected_image["data"] = base64.b64encode(image_data).decode()
                            selected_image["name"] = file.name
                        image_preview.value = f"📷 {file.name}"
                        image_preview.color = COLORS["success"]
                    else:
                        # Web: show friendly message
                        show_snackbar(self.page, "💡 Use desktop/mobile app for image upload")
                    self.page.update()
                except Exception as ex:
                    print(f"Image upload error: {ex}")
                    show_error_dialog(self.page, "Error", f"Failed: {str(ex)}")
        
        file_picker = ft.FilePicker(on_result=on_file_result)
        self.page.overlay.append(file_picker)
        
        notes_field = ft.TextField(
            label="Notes (optional)",
            hint_text="Paid via GCash",
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=12,
        )
        
        def confirm_payment(e):
            try:
                # Create settlement (image/notes are optional)
                response = db.create_settlement(config.CURRENT_TRIP_ID, from_id, to_id, amount_cents)
                
                if response.data and len(response.data) > 0:
                    settlement_id = response.data[0]['id']
                    
                    # Update with proof if provided (both are optional)
                    if selected_image.get("data") or (notes_field.value and notes_field.value.strip()):
                        try:
                            db.update_settlement_proof(
                                settlement_id, 
                                selected_image.get("data"), 
                                notes_field.value.strip() if notes_field.value else None
                            )
                        except Exception as proof_ex:
                            print(f"Proof upload error (non-critical): {proof_ex}")
                
                dlg.open = False
                self.page.overlay.remove(file_picker)
                self.page.update()
                
                show_snackbar(self.page, f"✓ Payment marked! {to_name} will confirm it.")
                if self.refresh_callback:
                    self.refresh_callback(None)
                
            except Exception as ex:
                print(f"Payment error: {ex}")
                show_error_dialog(self.page, "Error", f"Failed to record payment: {str(ex)}")
        
        def cancel_dialog(e):
            dlg.open = False
            self.page.overlay.remove(file_picker)
            self.page.update()
        
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Mark as Paid", size=20, weight="bold"),
            content=ft.Column([
                ft.Text(f"You → {to_name}", size=16, weight="bold"),
                ft.Text(amount_str, size=24, color=COLORS["success"], weight="bold"),
                ft.Divider(),
                ft.Text("Upload payment proof (optional):", size=12),
                ft.ElevatedButton(
                    "📷 Select Image",
                    on_click=pick_image,
                    style=ft.ButtonStyle(bgcolor=COLORS["accent"], color=COLORS["surface"])
                ),
                image_preview,
                ft.Container(height=8),
                notes_field,
                ft.Container(height=8),
                ft.Text(f"{to_name} will see this and can confirm/reject", 
                       size=11, italic=True, color=COLORS["text_secondary"]),
            ], tight=True, spacing=8, scroll=ft.ScrollMode.AUTO, height=450),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_dialog),
                ft.ElevatedButton(
                    "Mark as Paid",
                    on_click=confirm_payment,
                    style=ft.ButtonStyle(bgcolor=COLORS["success"], color=COLORS["surface"])
                ),
            ]
        )
        
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
    
    def _confirm_payment_received(self, settlement_id: str, payer_name: str, amount_str: str):
        """Confirm payment was received"""
        def do_confirm(e):
            try:
                db.confirm_settlement(settlement_id, config.CURRENT_USER_ID)
                show_snackbar(self.page, f"✓ Confirmed! Payment from {payer_name} marked complete.")
                confirm_dlg.open = False
                self.page.update()
                if self.refresh_callback:
                    self.refresh_callback(None)
            except Exception as ex:
                show_error_dialog(self.page, "Error", str(ex))
        
        def cancel(e):
            confirm_dlg.open = False
            self.page.update()
        
        confirm_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirm Payment?", size=20, weight="bold"),
            content=ft.Column([
                ft.Text(f"Confirm you received {amount_str} from {payer_name}?", size=14),
                ft.Container(height=8),
                ft.Container(
                    content=ft.Text("This will mark the payment as complete and update balances.", 
                                   size=12, italic=True),
                    padding=12,
                    bgcolor=COLORS["secondary"],
                    border_radius=8,
                )
            ], tight=True, spacing=8),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton(
                    "Confirm ✓",
                    on_click=do_confirm,
                    style=ft.ButtonStyle(bgcolor=COLORS["success"], color=COLORS["surface"])
                ),
            ]
        )
        
        self.page.dialog = confirm_dlg
        confirm_dlg.open = True
        self.page.update()
    
    def _reject_payment(self, settlement_id: str, payer_name: str, amount_str: str):
        """Reject payment"""
        reason_field = ft.TextField(
            label="Reason (optional but recommended)",
            hint_text="Amount incorrect, not received yet, wrong method...",
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=12,
        )
        
        def do_reject(e):
            try:
                reason = reason_field.value.strip() if reason_field.value else None
                db.reject_settlement(settlement_id, reason)
                show_snackbar(self.page, f"Payment rejected. {payer_name} will be notified.")
                reject_dlg.open = False
                self.page.update()
                if self.refresh_callback:
                    self.refresh_callback(None)
            except Exception as ex:
                show_error_dialog(self.page, "Error", str(ex))
        
        def cancel(e):
            reject_dlg.open = False
            self.page.update()
        
        reject_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Reject Payment?", color=COLORS["error"], size=20, weight="bold"),
            content=ft.Column([
                ft.Text(f"Reject {amount_str} payment from {payer_name}?", size=14),
                ft.Container(height=8),
                reason_field,
            ], tight=True, spacing=12),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton("Not Good ✗", on_click=do_reject,
                                 style=ft.ButtonStyle(bgcolor=COLORS["error"], color=COLORS["surface"])),
            ]
        )
        
        self.page.dialog = reject_dlg
        reject_dlg.open = True
        self.page.update()
    
    def _show_image_proof(self, image_base64: str):
        """Show image proof dialog"""
        if not image_base64:
            show_error_dialog(self.page, "No Image", "This payment has no proof image attached")
            return
        
        def close_img(e):
            img_dlg.open = False
            self.page.update()
        
        img_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Payment Proof", size=18, weight="bold"),
            content=ft.Image(
                src_base64=image_base64,
                width=400,
                height=400,
                fit=ft.ImageFit.CONTAIN,
            ),
            actions=[ft.TextButton("Close", on_click=close_img)]
        )
        
        self.page.dialog = img_dlg
        img_dlg.open = True
        self.page.update()
    
    def set_page_and_callback(self, page: ft.Page, refresh_callback):
        """Set page reference and refresh callback"""
        self.page = page
        self.refresh_callback = refresh_callback