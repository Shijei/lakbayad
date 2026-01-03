"""
Configuration and constants for LakBayad app
"""

# Add your Supabase credentials here
SUPABASE_URL = "https://upjrvfuszxkrqnaxexzu.supabase.co"
SUPABASE_KEY = "sb_publishable_-PsowdFaMCFuOcJCTRUYSw_coe8Sac8"

# Global state variables
CURRENT_USER_ID = None
CURRENT_TRIP_ID = None
CURRENT_TRIP_CREATOR = None  # Track who created current trip
LOCAL_EXPENSES = []
LOCAL_PARTICIPANTS = {}
LAST_SELECTED_PARTICIPANTS = set()
SHOW_OFFLINE_PREVIEW = False

# Khaki color palette
COLORS = {
    "primary": "#8B7355",      # Khaki brown
    "secondary": "#C9B896",    # Light khaki
    "accent": "#A0826D",       # Medium khaki
    "bg": "#F5F5DC",          # Beige
    "surface": "#FFFFFF",      # White
    "text": "#3E2723",        # Dark brown
    "text_secondary": "#6D4C41", # Medium brown
    "success": "#7CB342",     # Green
    "warning": "#FFA726",     # Orange
    "error": "#E53935",       # Red
}

# App settings
APP_TITLE = "LakBayad ₱"
APP_PORT = 8000