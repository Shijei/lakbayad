"""
Offline Status Indicator - Shows connection status to user
"""
import flet as ft
from ui.helpers import COLORS

def create_offline_indicator(page, db):
    """
    Create offline status indicator that updates based on connection
    
    Args:
        page: Flet page instance
        db: Database instance (HybridDatabase)
    """
    # Get current connection status
    try:
        status = db.get_connection_status()
        is_online = status['online']
        pending_sync = status['pending_sync']
    except:
        is_online = True
        pending_sync = 0
        
    if is_online and pending_sync == 0:
        # Online, all synced - show nothing or subtle indicator
        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.CLOUD_DONE, color=ft.colors.GREEN, size=16),
                ft.Text("Online", size=12, color=ft.colors.GREEN)
            ], tight=True, spacing=4),
            padding=8,
            visible=False  # Hide when everything is good
        )
    
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


class OfflineStatusBar:
    """Persistent offline status bar for appbar"""
    
    def __init__(self):
        self.container = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.CLOUD_DONE, color=ft.colors.GREEN, size=20),
            ], tight=True),
            padding=4,
            visible=False
        )
    
    def update_status(self, is_online, pending_sync=0):
        """Update status indicator"""
        if is_online and pending_sync == 0:
            # Online, all good
            self.container.content = ft.Row([
                ft.Icon(ft.Icons.CLOUD_DONE, color=ft.colors.GREEN, size=20),
            ], tight=True)
            self.container.bgcolor = None
            self.container.visible = False
            
        elif is_online and pending_sync > 0:
            # Syncing
            self.container.content = ft.Row([
                ft.ProgressRing(width=16, height=16, stroke_width=2, color=COLORS["warning"]),
                ft.Text(f"{pending_sync}", size=12, color=COLORS["warning"])
            ], tight=True, spacing=4)
            self.container.bgcolor = None
            self.container.visible = True
            
        else:
            # Offline
            self.container.content = ft.Row([
                ft.Icon(ft.Icons.CLOUD_OFF, color=COLORS["error"], size=20),
                ft.Text(f"{pending_sync}" if pending_sync > 0 else "", size=12)
            ], tight=True, spacing=4)
            self.container.bgcolor = ft.colors.RED_50
            self.container.visible = True
        
        return self.container