"""
AppBar Module - Navigation bar with user avatar and notifications
"""
import flet as ft
import config
from config import COLORS
from database import db


def create_appbar(page: ft.Page, current_user_data: dict, on_logout, update_callback=None):
    """
    Create AppBar with user avatar, notification bell, and logout
    
    Args:
        page: Flet page instance
        current_user_data: Dict with user info (display_name, id)
        on_logout: Callback for logout button
        update_callback: Optional callback to refresh appbar (for notification count)
    
    Returns:
        None (updates page.appbar directly)
    """
    
    # Check for unread notifications
    unread_count = 0
    try:
        notif_response = db.get_notifications(config.CURRENT_USER_ID, unread_only=True)
        unread_count = len(notif_response.data) if notif_response.data else 0
    except Exception as ex:
        print(f"Notification count error: {ex}")
    
    # Create user avatar with first letter
    first_letter = current_user_data.get('display_name', 'U')[0].upper()
    avatar = ft.Container(
        content=ft.Text(
            first_letter, 
            size=18, 
            weight="bold", 
            color=COLORS["surface"]
        ),
        width=40,
        height=40,
        border_radius=20,
        bgcolor=COLORS["accent"],
        alignment=ft.alignment.center,
    )
    
    # Create notification button with badge
    def open_notifications(e):
        show_notifications_dialog(page, update_callback)
    
    notif_button = ft.Stack([
        ft.IconButton(
            icon=ft.Icons.NOTIFICATIONS,
            icon_color=COLORS["surface"],
            tooltip=f"{unread_count} notifications" if unread_count > 0 else "Notifications",
            on_click=open_notifications,
        ),
        ft.Container(
            content=ft.Text(
                str(unread_count), 
                size=10, 
                weight="bold",
                color=COLORS["surface"]
            ),
            bgcolor=COLORS["error"],
            border_radius=10,
            padding=ft.padding.all(4),
            width=20,
            height=20,
            alignment=ft.alignment.center,
            right=5,
            top=5,
            visible=unread_count > 0
        )
    ])
    
    # Create AppBar
    page.appbar = ft.AppBar(
        leading=avatar,
        leading_width=60,
        title=ft.Text(
            current_user_data.get('display_name', 'User'), 
            size=16, 
            color=COLORS["surface"]
        ),
        center_title=False,
        bgcolor=COLORS["primary"],
        actions=[
            notif_button,
            ft.IconButton(
                icon=ft.Icons.LOGOUT,
                icon_color=COLORS["surface"],
                tooltip="Logout",
                on_click=on_logout
            )
        ]
    )
    page.update()


def show_notifications_dialog(page: ft.Page, update_appbar_callback=None):
    """
    Show notifications dialog with all user notifications
    
    Args:
        page: Flet page instance
        update_appbar_callback: Optional callback to refresh appbar after closing
    """
    notifications = []
    
    try:
        notif_response = db.get_notifications(config.CURRENT_USER_ID)
        notifications = notif_response.data if notif_response.data else []
    except Exception as ex:
        print(f"Notification error: {ex}")
    
    lv_notifications = ft.ListView(spacing=8, height=400)
    
    if not notifications:
        lv_notifications.controls.append(
            ft.Container(
                content=ft.Text(
                    "No notifications", 
                    italic=True, 
                    color=COLORS["text_secondary"],
                    size=14
                ),
                padding=20,
            )
        )
    else:
        for notif in notifications:
            is_unread = not notif.get('is_read', False)
            is_rejection = "reject" in notif['message'].lower()
            
            lv_notifications.controls.append(
                ft.Container(
                    content=ft.ListTile(
                        leading=ft.Icon(
                            ft.Icons.ERROR_OUTLINE if is_rejection else ft.Icons.INFO_OUTLINE,
                            color=COLORS["error"] if is_rejection else COLORS["primary"],
                            size=24
                        ),
                        title=ft.Text(
                            notif['message'], 
                            size=14, 
                            weight="bold" if is_unread else "normal"
                        ),
                        subtitle=ft.Text(
                            notif.get('created_at', '')[:16].replace('T', ' '), 
                            size=11,
                            color=COLORS["text_secondary"]
                        ),
                    ),
                    bgcolor=COLORS["secondary"] if is_unread else COLORS["surface"],
                    border_radius=12,
                    padding=4,
                    margin=ft.margin.only(bottom=4),
                )
            )
            
            # Mark as read
            if is_unread:
                try:
                    db.mark_notification_read(notif['id'])
                except:
                    pass
    
    def close_notif(e):
        dlg.open = False
        if update_appbar_callback:
            update_appbar_callback()
        page.update()
    
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("🔔 Notifications", size=20, weight="bold"),
        content=lv_notifications,
        actions=[
            ft.ElevatedButton(
                "Close", 
                on_click=close_notif,
                style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"])
            )
        ]
    )
    
    page.dialog = dlg
    dlg.open = True
    page.update()