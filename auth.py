"""
Authentication module - Login, Signup, Claim Code
"""
import flet as ft
import config
from config import COLORS
from database import db
from utils import generate_claim_code, hash_password


def create_auth_view(page: ft.Page, on_auth_success):
    """Create authentication UI with Login/Signup/Claim tabs"""
    
    def show_error_dialog(title: str, message: str):
        """Show error dialog - simpler approach"""
        def close_dlg(e):
            dlg_modal.open = False
            page.update()
        
        dlg_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, color=COLORS["error"], weight="bold"),
            content=ft.Text(message, color=COLORS["text"]),
            actions=[
                ft.TextButton("OK", on_click=close_dlg)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.dialog = dlg_modal
        dlg_modal.open = True
        page.update()
    
    def show_snackbar(message: str, error: bool = False):
        """Show snackbar notification"""
        page.snack_bar = ft.SnackBar(
            ft.Text(message, color=COLORS["surface"], size=14),
            bgcolor=COLORS["error"] if error else COLORS["success"],
            duration=3000
        )
        page.snack_bar.open = True
        page.update()
    
    # ==================== LOGIN ====================
    
    txt_login_email = ft.TextField(
        label="Email",
        hint_text="your@email.com",
        keyboard_type=ft.KeyboardType.EMAIL,
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
        hint_style=ft.TextStyle(color=COLORS["text_secondary"], size=14),
        on_submit=lambda e: login_account(e),  # Enter key triggers login
    )
    
    txt_login_password = ft.TextField(
        label="Password",
        password=True,
        can_reveal_password=True,
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
        hint_style=ft.TextStyle(color=COLORS["text_secondary"], size=14),
        on_submit=lambda e: login_account(e),  # Enter key triggers login
    )
    
    def login_account(e):
        """Login with email/password"""
        if not txt_login_email.value or not txt_login_password.value:
            show_error_dialog("Missing Fields", "Please enter both email and password")
            return
        
        email = txt_login_email.value.strip().lower()
        password = txt_login_password.value
        
        try:
            password_hash = hash_password(password)
            response = db.get_user_by_email(email)
            
            if not response.data:
                show_error_dialog("Email Not Found", "This email is not registered. Please sign up first.")
                return
            
            user = response.data[0]
            
            # Check if temp user
            if user.get('is_temp'):
                show_error_dialog("Account Not Claimed", "This account hasn't been claimed yet. Please use the claim code during signup.")
                return
            
            stored_hash = user.get('password_hash') or user.get('avatar_url')
            
            if not stored_hash:
                show_error_dialog("Invalid Account", "This account has no password. Please contact support.")
                return
            
            if stored_hash != password_hash:
                show_error_dialog("Incorrect Password", "The password you entered is incorrect. Please try again.")
                return
            
            # Success!
            config.CURRENT_USER_ID = user['id']
            show_snackbar(f"✓ Welcome back, {user['display_name']}!")
            on_auth_success(user)
            
        except Exception as ex:
            print(f"Login error: {ex}")
            show_error_dialog("Login Failed", f"An error occurred: {str(ex)}")
    
    btn_login = ft.Button(
        "Login",
        on_click=login_account,
        style=ft.ButtonStyle(bgcolor=COLORS["primary"], color=COLORS["surface"]),
        width=250,
        height=45
    )
    
    login_container = ft.Container(
        content=ft.Column([
            ft.Text("Login to Your Account", size=18, weight="bold", color=COLORS["text"]),
            txt_login_email,
            txt_login_password,
            btn_login,
        ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        width=300,
        visible=True
    )
    
    # ==================== SIGNUP ====================
    
    txt_signup_name = ft.TextField(
        label="Display Name",
        hint_text="John Doe",
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
        hint_style=ft.TextStyle(color=COLORS["text_secondary"], size=14),
        on_submit=lambda e: signup_account(e),
    )
    
    txt_signup_email = ft.TextField(
        label="Email",
        hint_text="your@email.com",
        keyboard_type=ft.KeyboardType.EMAIL,
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
        hint_style=ft.TextStyle(color=COLORS["text_secondary"], size=14),
        on_submit=lambda e: signup_account(e),
    )
    
    txt_signup_password = ft.TextField(
        label="Password",
        password=True,
        can_reveal_password=True,
        hint_text="At least 6 characters",
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
        hint_style=ft.TextStyle(color=COLORS["text_secondary"], size=14),
        on_submit=lambda e: signup_account(e),
    )
    
    txt_signup_claim_code = ft.TextField(
        label="Claim Code (Optional)",
        hint_text="RENA-ABC12 - if someone added you to a trip",
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
        hint_style=ft.TextStyle(color=COLORS["text_secondary"], size=14),
        on_submit=lambda e: signup_account(e),
    )
    
    def signup_account(e):
        """Create new account or claim existing temp account"""
        if not txt_signup_email.value or not txt_signup_password.value or not txt_signup_name.value:
            show_error_dialog("Missing Fields", "Please fill in name, email, and password")
            return
        
        email = txt_signup_email.value.strip().lower()
        password = txt_signup_password.value
        display_name = txt_signup_name.value.strip()
        claim_code = txt_signup_claim_code.value.strip().upper() if txt_signup_claim_code.value else None
        
        if len(password) < 6:
            show_error_dialog("Weak Password", "Password must be at least 6 characters")
            return
        
        try:
            # Check if email already exists
            check_email = db.get_user_by_email(email)
            if check_email.data:
                show_error_dialog("Email Taken", "This email is already registered. Please login instead.")
                return
            
            # If claim code provided, verify and claim temp account
            if claim_code:
                check_claim = db.get_user_by_claim_code(claim_code)
                
                if not check_claim.data:
                    show_error_dialog("Invalid Code", f"Claim code '{claim_code}' not found")
                    return
                
                temp_user = check_claim.data[0]
                
                if not temp_user['is_temp']:
                    show_error_dialog("Already Claimed", "This claim code has already been used")
                    return
                
                # Check if temp user has email (shouldn't happen but validate)
                if temp_user.get('email'):
                    show_error_dialog("Invalid Claim", "This account already has an email. Contact support.")
                    return
                
                # Update temp user with real credentials
                password_hash = hash_password(password)
                
                # Use httpx directly since it's a PATCH
                db.client.request(
                    "PATCH",
                    f"{db.url}/rest/v1/users",
                    params={"id": f"eq.{temp_user['id']}"},
                    json={
                        "email": email,
                        "display_name": display_name,
                        "password_hash": password_hash,
                        "is_temp": False
                    },
                    headers={**db.headers, "Prefer": "return=representation"}
                )
                
                config.CURRENT_USER_ID = temp_user['id']
                show_snackbar(f"✓ Account claimed! Welcome, {display_name}!")
                
                user = {
                    'id': temp_user['id'],
                    'email': email,
                    'display_name': display_name,
                    'claim_code': temp_user['claim_code'],
                    'is_temp': False
                }
                on_auth_success(user)
                return
            
            # Regular signup without claim code
            password_hash = hash_password(password)
            new_claim_code = generate_claim_code(display_name)
            
            response = db.create_user(email, display_name, password_hash, new_claim_code, is_temp=False)
            user = response.data[0]
            
            # Success!
            config.CURRENT_USER_ID = user['id']
            show_snackbar(f"✓ Account created! Welcome, {display_name}!")
            on_auth_success(user)
            
        except Exception as ex:
            print(f"Signup error: {ex}")
            show_error_dialog("Signup Failed", f"An error occurred: {str(ex)}")
    
    btn_signup = ft.Button(
        "Create Account",
        on_click=signup_account,
        style=ft.ButtonStyle(bgcolor=COLORS["success"], color=COLORS["surface"]),
        width=250,
        height=45
    )
    
    signup_container = ft.Container(
        content=ft.Column([
            ft.Text("Create New Account", size=18, weight="bold", color=COLORS["text"]),
            txt_signup_name,
            txt_signup_email,
            txt_signup_password,
            txt_signup_claim_code,
            btn_signup,
        ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        width=300,
        visible=False
    )
    
    # ==================== CLAIM CODE ====================
    
    txt_claim_code = ft.TextField(
        label="Enter Claim Code",
        hint_text="RENA-A1B2C",
        text_style=ft.TextStyle(size=16),
        bgcolor=COLORS["surface"],
        color=COLORS["text"],
        hint_style=ft.TextStyle(color=COLORS["text_secondary"], size=14),
        on_submit=lambda e: claim_account(e),  # Enter key triggers claim
    )
    
    def claim_account(e):
        """Claim account using code"""
        if not txt_claim_code.value:
            show_error_dialog("Missing Code", "Please enter a claim code")
            return
        
        claim_code = txt_claim_code.value.strip().upper()
        
        try:
            response = db.get_user_by_claim_code(claim_code)
            
            if not response.data:
                show_error_dialog("Invalid Code", f"No account found with code: {claim_code}")
                return
            
            user = response.data[0]
            
            # Success!
            config.CURRENT_USER_ID = user['id']
            show_snackbar(f"✓ Welcome, {user['display_name']}!")
            on_auth_success(user)
            
        except Exception as ex:
            print(f"Claim error: {ex}")
            show_error_dialog("Claim Failed", f"An error occurred: {str(ex)}")
    
    btn_claim = ft.Button(
        "Claim Account",
        on_click=claim_account,
        style=ft.ButtonStyle(bgcolor=COLORS["accent"], color=COLORS["surface"]),
        width=250,
        height=45
    )
    
    claim_container = ft.Container(
        content=ft.Column([
            ft.Text("Have a Claim Code?", size=18, weight="bold", color=COLORS["text"]),
            ft.Text(
                "If someone added you to a trip, use your claim code",
                size=12,
                color=COLORS["text_secondary"],
                text_align=ft.TextAlign.CENTER
            ),
            txt_claim_code,
            btn_claim,
        ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        width=300,
        visible=False
    )
    
    # ==================== TAB SWITCHING ====================
    
    def toggle_auth_mode(e):
        """Switch between login/signup"""
        mode = e.control.data
        login_container.visible = (mode == "login")
        signup_container.visible = (mode == "signup")
        page.update()
    
    # ==================== WELCOME CONTAINER ====================
    
    welcome_container = ft.Container(
        content=ft.Column([
            ft.Container(height=30),
            ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, size=70, color=COLORS["primary"]),
            ft.Text("LakBayad ₱", size=36, weight="bold", color=COLORS["primary"]),
            ft.Text("Trip Expense Splitter", size=16, color=COLORS["text_secondary"]),
            ft.Container(height=20),
            
            # Tab buttons
            ft.Row([
                ft.TextButton(
                    "Login",
                    data="login",
                    on_click=toggle_auth_mode,
                    style=ft.ButtonStyle(color=COLORS["primary"])
                ),
                ft.Text("|", color=COLORS["text_secondary"]),
                ft.TextButton(
                    "Sign Up",
                    data="signup",
                    on_click=toggle_auth_mode,
                    style=ft.ButtonStyle(color=COLORS["primary"])
                ),
            ], alignment=ft.MainAxisAlignment.CENTER),
            
            ft.Container(height=10),
            
            # Auth forms
            login_container,
            signup_container,
            
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        expand=True,
        bgcolor=COLORS["bg"]
    )
    
    return welcome_container