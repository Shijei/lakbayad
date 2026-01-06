"""
Configuration module - App settings and environment variables
"""
import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Load environment variables (securely)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Validate required environment variables
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "Missing required environment variables!\n"
        "Please set SUPABASE_URL and SUPABASE_KEY as environment variables.\n"
        "You can create a .env file or set them in your system/Render dashboard."
    )

# App Settings
APP_PORT = int(os.getenv("APP_PORT", "8000"))

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

# Global State (runtime only, not stored)
CURRENT_USER_ID = None
CURRENT_TRIP_ID = None
CURRENT_TRIP_CREATOR = None

# Offline Mode
LOCAL_EXPENSES = []
SHOW_OFFLINE_PREVIEW = True
LAST_SELECTED_PARTICIPANTS = set()