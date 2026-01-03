"""
Lightweight Database operations using httpx (no supabase package needed)
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
        
        # Add Prefer header for POST/PATCH to return data
        headers = self.headers.copy()
        if method in ["POST", "PATCH"]:
            headers["Prefer"] = "return=representation"
        
        response = self.client.request(method, url, params=params, json=json_data, headers=headers)
        response.raise_for_status()
        
        # Parse response
        if response.text:
            result = response.json()
            # Ensure result is always a list
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
        """Delete an expense permanently (cascade deletes participants)"""
        result = self._request("DELETE", "expenses", params={"id": f"eq.{expense_id}"})
        return type('Response', (), {'data': result})()
    
    # ==================== SETTLEMENT OPERATIONS ====================
    
    def create_settlement(self, trip_id: str, payer_id: str, receiver_id: str, amount_cents: int):
        """Create settlement record"""
        data = {
            "trip_id": trip_id,
            "payer_id": payer_id,
            "receiver_id": receiver_id,
            "amount_cents": amount_cents,
            "status": "pending"
        }
        result = self._request("POST", "settlements", json_data=data)
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
    
    def confirm_settlement(self, settlement_id: str, confirmed_by: str):
        """Confirm settlement payment received"""
        data = {
            "confirmed_by": confirmed_by,
            "confirmed_at": "now()",
            "status": "completed"
        }
        result = self._request("PATCH", "settlements", params={"id": f"eq.{settlement_id}"}, json_data=data)
        return type('Response', (), {'data': result})()
    
    # ==================== VOTING OPERATIONS ====================
    
    def create_delete_vote(self, trip_id: str, initiated_by: str):
        """Create a delete vote for a trip"""
        data = {
            "trip_id": trip_id,
            "initiated_by": initiated_by,
            "status": "pending",
            "votes": [initiated_by]  # Initiator automatically votes yes
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
        """Approve delete vote (all voted yes)"""
        result = self._request("PATCH", "delete_votes", params={"id": f"eq.{vote_id}"}, json_data={"status": "approved"})
        return type('Response', (), {'data': result})()
    
    def reject_delete_vote(self, vote_id: str):
        """Reject delete vote"""
        result = self._request("PATCH", "delete_votes", params={"id": f"eq.{vote_id}"}, json_data={"status": "rejected"})
        return type('Response', (), {'data': result})()
    
    # ==================== PARTICIPANT REMOVAL ====================
    
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