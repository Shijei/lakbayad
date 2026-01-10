"""
Dashboard Module - Main dashboard layout and coordination
"""
import flet as ft
import config
from config import COLORS
from database import db
from utils import format_currency, calculate_balances, optimize_settlements
from .helpers import show_snackbar, show_error_dialog, create_card_style


def create_dashboard_layout(page: ft.Page, all_participants: dict, all_trips: dict,
                            on_switch_trip, expenses_module, participants_module, 
                            settlements_module):
    """
    Create main dashboard layout that coordinates all components
    
    Args:
        page: Flet page instance
        all_participants: Dict of trip participants
        all_trips: Dict of user's trips
        on_switch_trip: Callback to switch trips
        expenses_module: Expenses component (from ui.expenses)
        participants_module: Participants component (from ui.participants)
        settlements_module: Settlements component (from ui.settlements)
    
    Returns:
        Tuple: (dashboard_container, refresh_function)
    """
    
    # UI Components
    txt_total_cost = ft.Text("Total: ₱0.00", size=32, weight="bold", color=COLORS["primary"])
    trip_name_text = ft.Text("", size=22, weight="bold", color=COLORS["text"])
    
    # Track settlement statuses
    pending_settlements_tracker = {}
    settlements_status = {}
    
    def refresh_dashboard(e=None):
        """Refresh all dashboard data"""
        if not config.CURRENT_TRIP_ID:
            return
        
        # Update trip name
        if config.CURRENT_TRIP_ID in all_trips:
            trip_name_text.value = all_trips[config.CURRENT_TRIP_ID]['name']
        
        try:
            # Fetch expenses
            response = db.get_trip_expenses(config.CURRENT_TRIP_ID)
            expenses_data = []
            
            for expense in response.data:
                expenses_data.append({
                    'id': expense['id'],
                    'paid_by_id': expense['paid_by_id'],
                    'amount_cents': expense['amount_cents'],
                    'category': expense['category'],
                    'description': expense['description'],
                    'participants': expense['expense_participants'],
                    'synced': True
                })
            
            # Add offline expenses if enabled
            if config.SHOW_OFFLINE_PREVIEW:
                for local_exp in config.LOCAL_EXPENSES:
                    expenses_data.append({**local_exp, 'synced': False})
            
            # Calculate totals and balances
            total_cents = sum(exp['amount_cents'] for exp in expenses_data)
            txt_total_cost.value = f"Total: {format_currency(total_cents)}"
            
            balances_dict, _ = calculate_balances(expenses_data)
            
            balances = {}
            for user_id, balance in balances_dict.items():
                balances[user_id] = {
                    'owes': max(0, -balance),
                    'is_owed': max(0, balance)
                }
            
            settlements = optimize_settlements(balances_dict)
            
            # Fetch ALL settlement statuses for this trip
            try:
                all_settlements_response = db._request("GET", "settlements", params={
                    "trip_id": f"eq.{config.CURRENT_TRIP_ID}"
                })
                settlements_status.clear()
                for settlement_record in all_settlements_response:
                    key = f"{settlement_record['payer_id']}_{settlement_record['receiver_id']}"
                    # Store both status AND amount to validate later
                    settlements_status[key] = {
                        'status': settlement_record['status'],
                        'amount_cents': settlement_record['amount_cents'],
                        'id': settlement_record['id']
                    }
            except Exception as status_ex:
                print(f"Settlement status fetch error: {status_ex}")
            
            # Fetch pending settlements where current user is PAYER
            try:
                payer_pending = db.get_pending_settlements_for_payer(
                    config.CURRENT_USER_ID,
                    config.CURRENT_TRIP_ID
                )
                pending_settlements_tracker.clear()
                if payer_pending.data:
                    for p in payer_pending.data:
                        key = f"{p['payer_id']}_{p['receiver_id']}_{p['amount_cents']}"
                        pending_settlements_tracker[key] = True
            except Exception as track_ex:
                print(f"Pending tracking error: {track_ex}")
            
            # Fetch pending payments for receiver
            try:
                pending_response = db.get_pending_settlements_for_receiver(
                    config.CURRENT_USER_ID, 
                    config.CURRENT_TRIP_ID
                )
                pending_payments = pending_response.data if pending_response.data else []
            except:
                pending_payments = []
            
            # Fetch payment history
            try:
                history_response = db.get_payment_history(config.CURRENT_TRIP_ID)
                payment_history = history_response.data if history_response.data else []
            except:
                payment_history = []
            
            # Update all components
            expenses_module.update_list(expenses_data, all_participants)
            settlements_module.update_settlements(
                settlements, 
                all_participants,
                pending_settlements_tracker,
                settlements_status
            )
            settlements_module.update_pending_payments(pending_payments, all_participants)
            settlements_module.update_payment_history(payment_history)
            settlements_module.update_balances(balances, all_participants)
            
            page.update()
            
        except Exception as ex:
            print(f"Dashboard error: {ex}")
            show_error_dialog(page, "Error", f"Failed to refresh: {str(ex)}")
    
    # Build header
    trip_header = ft.Container(
        content=ft.Row([
            trip_name_text,
            ft.Row([
                ft.IconButton(
                    icon=ft.Icons.PEOPLE,
                    tooltip="View Participants",
                    icon_color=COLORS["accent"],
                    icon_size=24,
                    on_click=lambda e: participants_module.show_dialog(page, all_participants, refresh_dashboard)
                ),
                ft.IconButton(
                    icon=ft.Icons.SWAP_HORIZ,
                    tooltip="Switch Trip",
                    icon_color=COLORS["primary"],
                    icon_size=24,
                    on_click=lambda e: on_switch_trip()
                )
            ], spacing=4)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        **create_card_style()
    )
    
    # Build dashboard
    dashboard_container = ft.Container(
        content=ft.Column([
            trip_header,
            ft.Container(content=txt_total_cost, **create_card_style()),
            expenses_module.create_section(page, all_participants, refresh_dashboard),
            settlements_module.create_pending_section(),
            settlements_module.create_settlements_section(),
            settlements_module.create_balances_section(),
            settlements_module.create_history_section(),
        ], scroll=ft.ScrollMode.AUTO, spacing=0),
        expand=True,
        bgcolor=COLORS["bg"],
        padding=20,
    )
    
    return dashboard_container, refresh_dashboard