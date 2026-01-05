"""
Helpers Module - Shared UI utilities and helpers
"""
import flet as ft
from config import COLORS


def show_snackbar(page: ft.Page, message: str, error: bool = False):
    """
    Show snackbar message
    
    Args:
        page: Flet page instance
        message: Message to display
        error: If True, show error style (red background)
    """
    snack_bar = ft.SnackBar(
        ft.Text(message, color=COLORS["surface"], size=14),
        bgcolor=COLORS["error"] if error else COLORS["success"],
        duration=3000
    )
    page.overlay.append(snack_bar)
    snack_bar.open = True
    page.update()


def show_error_dialog(page: ft.Page, title: str, message: str):
    """
    Show error dialog
    
    Args:
        page: Flet page instance
        title: Dialog title
        message: Error message
    """
    def close_error(e):
        error_dlg.open = False
        page.update()
    
    error_dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(title, size=18, weight="bold", color=COLORS["error"]),
        content=ft.Text(message, size=14),
        actions=[
            ft.TextButton("OK", on_click=close_error)
        ]
    )
    page.dialog = error_dlg
    error_dlg.open = True
    page.update()


def create_card_style():
    """
    Get consistent card styling
    
    Returns:
        Dict with card style properties
    """
    return {
        "padding": 24,
        "bgcolor": COLORS["surface"],
        "border_radius": 16,
        "margin": ft.margin.only(bottom=16),
    }


def format_participant_name(participant_data: dict, user_id: str = None, current_user_id: str = None):
    """
    Format participant display name with override and (You) suffix
    
    Args:
        participant_data: Dict with display_name and display_name_override
        user_id: User ID to check if it's current user
        current_user_id: Current user's ID
    
    Returns:
        Formatted name string
    """
    name = participant_data.get('display_name_override') or participant_data.get('display_name', 'Unknown')
    
    if user_id and current_user_id and user_id == current_user_id:
        return f"{name} (You)"
    
    return name