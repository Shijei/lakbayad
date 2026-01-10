"""
Lightweight Database operations using httpx (no supabase package needed)
WITH SETTLEMENT CONFIRMATION SYSTEM + NOTIFICATIONS
"""
import httpx
from typing import Optional, List, Dict
import config

class Database:
    def __init__(self):
        self.url = config.SUPABASE_URL
        self.key = config.SUPABASE_KEY
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        self.client = httpx.Client(headers=self.headers, timeout=30.0)
        print("✓ Database connected")
    
    def _request(self, method: str, table: str, params: dict = None, json_data: dict = None):
        """Make HTTP request to Supabase"""
        url = f"{self.url}/rest/v1/{table}"
        
        headers = self.headers.copy()
        if method in ["POST", "PATCH"]:
            headers["Prefer"] = "return=representation"
        
        response = self.client.request(method, url, params=params, json=json_data, headers=headers)
        response.raise_for_status()
        
        if response.text:
            result = response.json()
            if not isinstance(result, list):
                result = [result] if result else []
            return result
        return []
    
    # ==================== USER OPERATIONS ====================
    
    def create_user(self, email: str, display_name: str, password_hash: str, claim_code: str, is_temp: bool = False):
        """Create new user"""
        data = {
            "email": email,
            "display_name": display_name,
            "password_hash": password_hash,
            "claim_code": claim_code,
            "is_temp": is_temp
        }
        result = self._request("POST", "users", json_data=data)
        return type('Response', (), {'data': result if isinstance(result, list) else [result]})()
    
    def get_user_by_email(self, email: str):
        """Get user by email"""
        result = self._request("GET", "users", params={"email": f"eq.{email}"})
        return type('Response', (), {'data': result})()
    
    def get_user_by_claim_code(self, claim_code: str):
        """Get user by claim code"""
        result = self._request("GET", "users", params={"claim_code": f"eq.{claim_code}"})
        return type('Response', (), {'data': result})()
    
    def get_user_by_id(self, user_id: str):
        """Get user by ID"""
        result = self._request("GET", "users", params={"id": f"eq.{user_id}"})
        return type('Response', (), {'data': result})()
    
    # ==================== TRIP OPERATIONS ====================
    
    def create_trip(self, name: str, invite_code: str, created_by: str = None):
        """Create new trip"""
        data = {"name": name, "is_active": True, "invite_code": invite_code}
        if created_by:
            data["created_by"] = created_by
        result = self._request("POST", "trips", json_data=data)
        return type('Response', (), {'data': result if isinstance(result, list) else [result]})()
    
    def get_user_trips(self, user_id: str):
        """Get all trips for a user"""
        result = self._request("GET", "trip_members", params={
            "user_id": f"eq.{user_id}",
            "select": "trips(*)"
        })
        return type('Response', (), {'data': result})()
    
    def get_trip_by_invite_code(self, invite_code: str):
        """Get trip by invite code"""
        result = self._request("GET", "trips", params={"invite_code": f"eq.{invite_code}"})
        return type('Response', (), {'data': result})()
    
    def archive_trip(self, trip_id: str):
        """Archive a trip"""
        result = self._request("PATCH", "trips", params={"id": f"eq.{trip_id}"}, json_data={"is_active": False})
        return type('Response', (), {'data': result})()
    
    def delete_trip(self, trip_id: str):
        """Delete trip and all related data (CASCADE DELETE)"""
        try:
            # 1. Delete all settlements for this trip
            self._request("DELETE", "settlements", params={"trip_id": f"eq.{trip_id}"})
            
            # 2. Delete all expense_participants for expenses in this trip
            # First get all expense IDs
            expenses = self._request("GET", "expenses", params={"trip_id": f"eq.{trip_id}", "select": "id"})
            if expenses:
                for exp in expenses:
                    exp_id = exp.get('id')
                    if exp_id:
                        self._request("DELETE", "expense_participants", params={"expense_id": f"eq.{exp_id}"})
            
            # 3. Delete all expenses
            self._request("DELETE", "expenses", params={"trip_id": f"eq.{trip_id}"})
            
            # 4. Delete all trip members (NOT the users themselves, just the association)
            self._request("DELETE", "trip_members", params={"trip_id": f"eq.{trip_id}"})
            
            # 5. Finally, delete the trip itself
            result = self._request("DELETE", "trips", params={"id": f"eq.{trip_id}"})
            
            return type('Response', (), {'data': result})()
        except Exception as e:
            print(f"Error deleting trip: {e}")
            raise
    
    def add_user_to_trip(self, trip_id: str, user_id: str):
        """Add user to trip"""
        data = {"trip_id": trip_id, "user_id": user_id}
        result = self._request("POST", "trip_members", json_data=data)
        return type('Response', (), {'data': result if isinstance(result, list) else [result]})()
    
    def check_trip_membership(self, trip_id: str, user_id: str):
        """Check if user is member of trip"""
        result = self._request("GET", "trip_members", params={
            "trip_id": f"eq.{trip_id}",
            "user_id": f"eq.{user_id}"
        })
        return type('Response', (), {'data': result})()
    
    # ==================== PARTICIPANT OPERATIONS ====================
    
    def get_trip_participants(self, trip_id: str):
        """Get all participants in a trip"""
        result = self._request("GET", "trip_members", params={
            "trip_id": f"eq.{trip_id}",
            "select": "*,users(*)"
        })
        return type('Response', (), {'data': result})()
    
    # ==================== EXPENSE OPERATIONS ====================
    
    def create_expense(self, trip_id: str, paid_by_id: str, amount_cents: int, category: str, description: str):
        """Create new expense"""
        data = {
            "trip_id": trip_id,
            "paid_by_id": paid_by_id,
            "amount_cents": amount_cents,
            "category": category,
            "description": description
        }
        result = self._request("POST", "expenses", json_data=data)
        return type('Response', (), {'data': result if isinstance(result, list) else [result]})()
    
    def add_expense_participants(self, participants_data: List[Dict]):
        """Add participants to an expense"""
        result = self._request("POST", "expense_participants", json_data=participants_data)
        return type('Response', (), {'data': result})()
    
    def get_trip_expenses(self, trip_id: str):
        """Get all expenses for a trip"""
        result = self._request("GET", "expenses", params={
            "trip_id": f"eq.{trip_id}",
            "select": "*,expense_participants(*)"
        })
        return type('Response', (), {'data': result})()
    
    def delete_expense(self, expense_id: str):
        """Delete an expense permanently"""
        result = self._request("DELETE", "expenses", params={"id": f"eq.{expense_id}"})
        return type('Response', (), {'data': result})()
    
    # ==================== SETTLEMENT OPERATIONS (FIXED) ====================
    
    def create_settlement(self, trip_id: str, payer_id: str, receiver_id: str, amount_cents: int):
        """Create settlement record and notify receiver"""
        data = {
            "trip_id": trip_id,
            "payer_id": payer_id,
            "receiver_id": receiver_id,
            "amount_cents": amount_cents,
            "status": "pending"
        }
        result = self._request("POST", "settlements", json_data=data)
        
        # Create notification for receiver
        try:
            # Get payer name
            payer = self._request("GET", "users", params={"id": f"eq.{payer_id}"})
            payer_name = payer[0]['display_name'] if payer else 'Someone'
            
            message = f"💰 {payer_name} marked payment of ₱{amount_cents/100:.2f} as paid. Please confirm!"
            notif_data = {
                "user_id": receiver_id,
                "message": message,
                "is_read": False
            }
            self._request("POST", "notifications", json_data=notif_data)
        except Exception as notif_err:
            print(f"Notification creation failed: {notif_err}")
            pass  # Notifications optional
        
        return type('Response', (), {'data': result})()
    
    def update_settlement_proof(self, settlement_id: str, proof_image: str = None, notes: str = None):
        """Update settlement with payment proof"""
        data = {}
        if proof_image:
            data["proof_image_base64"] = proof_image
        if notes:
            data["proof_notes"] = notes
        result = self._request("PATCH", "settlements", params={"id": f"eq.{settlement_id}"}, json_data=data)
        return type('Response', (), {'data': result})()
    
    def get_pending_settlements_for_receiver(self, receiver_id: str, trip_id: str = None):
        """Get pending settlements where user is receiver"""
        params = {
            "receiver_id": f"eq.{receiver_id}",
            "status": "eq.pending",
            "select": "*,payer:payer_id(display_name),receiver:receiver_id(display_name),trips(name)"
        }
        
        if trip_id:
            params["trip_id"] = f"eq.{trip_id}"
        
        result = self._request("GET", "settlements", params=params)
        return type('Response', (), {'data': result})()
    
    def get_pending_settlements_for_payer(self, payer_id: str, trip_id: str = None):
        """Get pending settlements where user is payer (NEW - for tracking)"""
        params = {
            "payer_id": f"eq.{payer_id}",
            "status": "eq.pending"
        }
        
        if trip_id:
            params["trip_id"] = f"eq.{trip_id}"
        
        result = self._request("GET", "settlements", params=params)
        return type('Response', (), {'data': result})()
    
    def get_payment_history(self, trip_id: str):
        """Get confirmed and voided settlements for a trip"""
        result = self._request("GET", "settlements", params={
            "trip_id": f"eq.{trip_id}",
            "status": "in.(confirmed,voided)",  # Include both confirmed AND voided
            "select": "*,payer:payer_id(display_name),receiver:receiver_id(display_name)",
            "order": "confirmed_at.desc.nullslast,created_at.desc",  # Show confirmed first, then voided
            "limit": "15"  # Show more to include voided ones
        })
        return type('Response', (), {'data': result})()
    
    def confirm_settlement(self, settlement_id: str, confirmed_by: str):
        """Confirm a settlement and notify payer"""
        try:
            # Get settlement details first
            settlement = self._request("GET", "settlements", params={"id": f"eq.{settlement_id}"})
            
            if settlement and len(settlement) > 0:
                payer_id = settlement[0]['payer_id']
                amount_cents = settlement[0]['amount_cents']
                
                # Update status
                data = {
                    "status": "confirmed",
                    "confirmed_by": confirmed_by,
                    "confirmed_at": "now()"
                }
                result = self._request("PATCH", "settlements", params={"id": f"eq.{settlement_id}"}, json_data=data)
                
                # Create notification for payer
                try:
                    message = f"✓ Payment of ₱{amount_cents/100:.2f} was confirmed!"
                    notif_data = {
                        "user_id": payer_id,
                        "message": message,
                        "is_read": False
                    }
                    self._request("POST", "notifications", json_data=notif_data)
                except Exception as notif_err:
                    print(f"Notification creation failed: {notif_err}")
                    pass  # Notifications optional
                
                return type('Response', (), {'data': result})()
        except Exception as ex:
            print(f"Confirm settlement error: {ex}")
            # Fall back to simple update if fetch fails
            data = {
                "status": "confirmed",
                "confirmed_by": confirmed_by,
                "confirmed_at": "now()"
            }
            result = self._request("PATCH", "settlements", params={"id": f"eq.{settlement_id}"}, json_data=data)
            return type('Response', (), {'data': result})()
    
    def reject_settlement(self, settlement_id: str, reason: str = None):
        """Reject a settlement and create notification for payer"""
        # Get settlement details first
        try:
            settlement = self._request("GET", "settlements", params={"id": f"eq.{settlement_id}"})
            
            if settlement and len(settlement) > 0:
                payer_id = settlement[0]['payer_id']
                amount_cents = settlement[0]['amount_cents']
                
                # Update status
                data = {
                    "status": "rejected",
                    "rejected_reason": reason
                }
                result = self._request("PATCH", "settlements", params={"id": f"eq.{settlement_id}"}, json_data=data)
                
                # Create notification for payer
                try:
                    message = f"Payment of ₱{amount_cents/100:.2f} was rejected"
                    if reason:
                        message += f": {reason}"
                    
                    notif_data = {
                        "user_id": payer_id,
                        "message": message,
                        "is_read": False
                    }
                    self._request("POST", "notifications", json_data=notif_data)
                except Exception as notif_err:
                    print(f"Notification creation failed: {notif_err}")
                    pass  # Notifications optional
                
                return type('Response', (), {'data': result})()
        except Exception as ex:
            print(f"Reject settlement error: {ex}")
            raise
    
    def get_notifications(self, user_id: str, unread_only: bool = False):
        """Get notifications for user"""
        params = {"user_id": f"eq.{user_id}", "order": "created_at.desc"}
        if unread_only:
            params["is_read"] = "eq.false"
        
        try:
            result = self._request("GET", "notifications", params=params)
            return type('Response', (), {'data': result})()
        except:
            return type('Response', (), {'data': []})()
    
    def mark_notification_read(self, notification_id: str):
        """Mark notification as read"""
        try:
            result = self._request("PATCH", "notifications", 
                                  params={"id": f"eq.{notification_id}"}, 
                                  json_data={"is_read": True})
            return type('Response', (), {'data': result})()
        except:
            return type('Response', (), {'data': []})()
    
    # ==================== VOTING OPERATIONS ====================
    
    def create_delete_vote(self, trip_id: str, initiated_by: str):
        """Create a delete vote for a trip"""
        data = {
            "trip_id": trip_id,
            "initiated_by": initiated_by,
            "status": "pending",
            "votes": [initiated_by]
        }
        result = self._request("POST", "delete_votes", json_data=data)
        return type('Response', (), {'data': result})()
    
    def get_pending_delete_vote(self, trip_id: str):
        """Get pending delete vote for a trip"""
        result = self._request("GET", "delete_votes", params={
            "trip_id": f"eq.{trip_id}",
            "status": f"eq.pending"
        })
        return type('Response', (), {'data': result})()
    
    def add_delete_vote(self, vote_id: str, user_id: str, current_votes: list):
        """Add a user's vote to delete"""
        new_votes = current_votes + [user_id] if user_id not in current_votes else current_votes
        result = self._request("PATCH", "delete_votes", params={"id": f"eq.{vote_id}"}, json_data={"votes": new_votes})
        return type('Response', (), {'data': result})()
    
    def approve_delete_vote(self, vote_id: str):
        """Approve delete vote"""
        result = self._request("PATCH", "delete_votes", params={"id": f"eq.{vote_id}"}, json_data={"status": "approved"})
        return type('Response', (), {'data': result})()
    
    def reject_delete_vote(self, vote_id: str):
        """Reject delete vote"""
        result = self._request("PATCH", "delete_votes", params={"id": f"eq.{vote_id}"}, json_data={"status": "rejected"})
        return type('Response', (), {'data': result})()
    
    # ==================== PARTICIPANT MANAGEMENT ====================
    
    def remove_participant(self, trip_id: str, user_id: str):
        """Remove participant from trip"""
        result = self._request("DELETE", "trip_members", params={
            "trip_id": f"eq.{trip_id}",
            "user_id": f"eq.{user_id}"
        })
        return type('Response', (), {'data': result})()
    
    def update_participant_nickname(self, trip_id: str, user_id: str, nickname: str):
        """Set trip-specific nickname for participant"""
        result = self._request("PATCH", "trip_members", params={
            "trip_id": f"eq.{trip_id}",
            "user_id": f"eq.{user_id}"
        }, json_data={"display_name_override": nickname})
        return type('Response', (), {'data': result})()
    
    def clear_participant_nickname(self, trip_id: str, user_id: str):
        """Clear trip-specific nickname"""
        result = self._request("PATCH", "trip_members", params={
            "trip_id": f"eq.{trip_id}",
            "user_id": f"eq.{user_id}"
        }, json_data={"display_name_override": None})
        return type('Response', (), {'data': result})()

# Singleton instance
db = Database()

# Wrap with offline support
try:
    from offline_db import OfflineDB
    from hybrid_db import HybridDatabase
    
    _offline_db = OfflineDB("lakbayad_cache.db")
    db = HybridDatabase(db, _offline_db)
    print("✓ Offline mode enabled")
except ImportError as e:
    print("⚠ Offline mode not available:", e)
except Exception as e:
    print("⚠ Offline mode failed to initialize:", e)