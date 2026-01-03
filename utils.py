"""
Utility helper functions
"""
import random
import string
import hashlib
from collections import defaultdict
import heapq
from typing import List, Dict
from config import COLORS


def generate_claim_code(display_name: str) -> str:
    """Generate a claim code like RENA-A1B2C"""
    name_part = display_name[:4].upper().replace(" ", "")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{name_part}-{random_part}"


def generate_invite_code() -> str:
    """Generate trip invite code"""
    return 'TRIP-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def normalize_name(name: str) -> str:
    """Normalize name: lowercase, strip whitespace"""
    return name.strip().lower()


def format_currency(cents: int) -> str:
    """Format centavos to peso string"""
    pesos = cents / 100
    return f"₱{pesos:,.2f}"


def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def calculate_balances(expenses_data: List[Dict]) -> tuple:
    """Calculate who owes whom based on expenses"""
    balances = defaultdict(int)
    total_cents = 0
    all_participant_ids = set()
    
    for expense in expenses_data:
        paid_by_id = expense['paid_by_id']
        amount_cents = expense['amount_cents']
        participants = expense.get('participants', [])
        
        total_cents += amount_cents
        balances[paid_by_id] += amount_cents
        
        for p in participants:
            all_participant_ids.add(p['user_id'])
            balances[p['user_id']] -= p['share_amount_cents']
    
    return dict(balances), total_cents


def optimize_settlements(balances: Dict[str, int]) -> List[Dict]:
    """Optimize settlements using greedy algorithm"""
    settlements = []
    
    creditors = []
    debtors = []
    
    for user_id, balance in balances.items():
        if balance > 0:
            heapq.heappush(creditors, (-balance, user_id))
        elif balance < 0:
            heapq.heappush(debtors, (balance, user_id))
    
    while creditors and debtors:
        credit_amt, creditor_id = heapq.heappop(creditors)
        debt_amt, debtor_id = heapq.heappop(debtors)
        
        credit_amt = -credit_amt
        debt_amt = -debt_amt
        
        settlement_amt = min(credit_amt, debt_amt)
        
        settlements.append({
            'from_id': debtor_id,
            'to_id': creditor_id,
            'amount_cents': settlement_amt
        })
        
        if credit_amt > settlement_amt:
            heapq.heappush(creditors, (-(credit_amt - settlement_amt), creditor_id))
        if debt_amt > settlement_amt:
            heapq.heappush(debtors, (-(debt_amt - settlement_amt), debtor_id))
    
    return settlements


def get_user_expense_breakdown(user_id: str, expenses_data: List[Dict], all_participants: Dict) -> Dict:
    """Get detailed expense breakdown for a user"""
    paid_expenses = []
    owes_expenses = []
    total_paid = 0
    total_owes = 0
    
    for expense in expenses_data:
        # Check if user paid this expense
        if expense['paid_by_id'] == user_id:
            paid_expenses.append({
                'description': expense['description'],
                'category': expense['category'],
                'amount_cents': expense['amount_cents']
            })
            total_paid += expense['amount_cents']
        
        # Check if user owes for this expense
        for participant in expense.get('participants', []):
            if participant['user_id'] == user_id:
                owes_expenses.append({
                    'description': expense['description'],
                    'category': expense['category'],
                    'share_cents': participant['share_amount_cents'],
                    'split_with': [all_participants.get(p['user_id'], {}).get('display_name', 'Unknown') 
                                  for p in expense['participants'] if p['user_id'] != user_id]
                })
                total_owes += participant['share_amount_cents']
    
    balance = total_paid - total_owes
    
    return {
        'paid': paid_expenses,
        'owes': owes_expenses,
        'total_paid': total_paid,
        'total_owes': total_owes,
        'balance': balance
    }
