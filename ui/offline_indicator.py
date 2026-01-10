"""
Offline Status Indicator - Shows connection status to user
"""
import flet as ft
from ui.helpers import COLORS

def create_offline_indicator(page, db):
    """
    Create offline status indicator that checks connection dynamically
    
    Args:
        page: Flet page instance
        db: Database instance (HybridDatabase)
    
    Returns:
        Container with status indicator
    """
    # Get current connection status
    try:
        if hasattr(db, 'get_connection_status'):
            status = db.get_connection_status()
            is_online = status.get('online', True)
            pending_sync = status.get('pending_sync', 0)
        else:
            is_online = True
            pending_sync = 0
    except:
        is_online = True
        pending_sync = 0
    
    if is_online and pending_sync == 0:
        # Online, all synced - hide indicator
        return ft.Container(visible=False)
    
    elif is_online and pending_sync > 0:
        # Online but has pending changes
        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.CLOUD_UPLOAD, color=COLORS["warning"], size=16),
                ft.Text(f"Syncing {pending_sync}...", size=12, color=COLORS["warning"])
            ], tight=True, spacing=4),
            padding=8,
            bgcolor=ft.colors.ORANGE_50,
            border_radius=8,
        )
    
    else:
        # Offline mode
        status_text = "Offline Mode"
        if pending_sync > 0:
            status_text += f" ({pending_sync} pending)"
        
        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.CLOUD_OFF, color=COLORS["error"], size=16),
                ft.Text(status_text, size=12, color=COLORS["error"], weight="bold")
            ], tight=True, spacing=4),
            padding=8,
            bgcolor=ft.colors.RED_50,
            border_radius=8,
        )