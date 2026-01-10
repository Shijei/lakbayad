"""
Offline Database Module - SQLite caching for full offline support
"""
import sqlite3
import json
import os
from datetime import datetime

class OfflineDB:
    """Local SQLite database for offline caching"""
    
    def __init__(self, db_path="lakbayad_cache.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trips table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                invite_code TEXT,
                is_active INTEGER,
                created_by TEXT,
                created_at TEXT,
                synced INTEGER DEFAULT 1,
                last_updated TEXT
            )
        """)
        
        # Participants table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                trip_id TEXT,
                user_id TEXT,
                display_name TEXT,
                display_name_override TEXT,
                synced INTEGER DEFAULT 1,
                PRIMARY KEY (trip_id, user_id)
            )
        """)
        
        # Expenses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id TEXT PRIMARY KEY,
                trip_id TEXT,
                paid_by_id TEXT,
                amount_cents INTEGER,
                category TEXT,
                description TEXT,
                created_at TEXT,
                synced INTEGER DEFAULT 1,
                local_only INTEGER DEFAULT 0
            )
        """)
        
        # Expense participants table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expense_participants (
                expense_id TEXT,
                user_id TEXT,
                share_amount_cents INTEGER,
                synced INTEGER DEFAULT 1,
                PRIMARY KEY (expense_id, user_id)
            )
        """)
        
        # Settlements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settlements (
                id TEXT PRIMARY KEY,
                trip_id TEXT,
                payer_id TEXT,
                receiver_id TEXT,
                amount_cents INTEGER,
                status TEXT,
                proof_image_base64 TEXT,
                proof_notes TEXT,
                created_at TEXT,
                confirmed_at TEXT,
                synced INTEGER DEFAULT 1,
                local_only INTEGER DEFAULT 0
            )
        """)
        
        # Sync queue table (for offline changes)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                table_name TEXT,
                data TEXT,
                created_at TEXT,
                attempts INTEGER DEFAULT 0
            )
        """)
        
        conn.commit()
        conn.close()
    
    # ==================== CACHE MANAGEMENT ====================
    
    def cache_trip(self, trip_data):
        """Cache trip data locally"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO trips 
            (id, name, invite_code, is_active, created_by, created_at, synced, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            trip_data['id'],
            trip_data['name'],
            trip_data.get('invite_code'),
            trip_data.get('is_active', True),
            trip_data.get('created_by'),
            trip_data.get('created_at'),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def cache_participants(self, trip_id, participants):
        """Cache participants for a trip"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for user_id, user_data in participants.items():
            cursor.execute("""
                INSERT OR REPLACE INTO participants
                (trip_id, user_id, display_name, display_name_override, synced)
                VALUES (?, ?, ?, ?, 1)
            """, (
                trip_id,
                user_id,
                user_data.get('display_name'),
                user_data.get('display_name_override')
            ))
        
        conn.commit()
        conn.close()
    
    def cache_expense(self, expense_data):
        """Cache expense data locally"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Cache expense
        cursor.execute("""
            INSERT OR REPLACE INTO expenses
            (id, trip_id, paid_by_id, amount_cents, category, description, created_at, synced, local_only)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            expense_data['id'],
            expense_data['trip_id'],
            expense_data['paid_by_id'],
            expense_data['amount_cents'],
            expense_data.get('category', 'Other'),
            expense_data.get('description', ''),
            expense_data.get('created_at', datetime.now().isoformat()),
            1,
            0
        ))
        
        # Cache expense participants
        if 'expense_participants' in expense_data:
            for participant in expense_data['expense_participants']:
                cursor.execute("""
                    INSERT OR REPLACE INTO expense_participants
                    (expense_id, user_id, share_amount_cents, synced)
                    VALUES (?, ?, ?, 1)
                """, (
                    expense_data['id'],
                    participant['user_id'],
                    participant['share_amount_cents']
                ))
        
        conn.commit()
        conn.close()
    
    # ==================== RETRIEVE CACHED DATA ====================
    
    def get_cached_trips(self):
        """Get all cached trips"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trips WHERE is_active = 1")
        rows = cursor.fetchall()
        
        trips = {}
        for row in rows:
            trips[row[0]] = {
                'id': row[0],
                'name': row[1],
                'invite_code': row[2],
                'is_active': bool(row[3]),
                'created_by': row[4],
                'created_at': row[5]
            }
        
        conn.close()
        return trips
    
    def get_cached_participants(self, trip_id):
        """Get cached participants for a trip"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id, display_name, display_name_override
            FROM participants
            WHERE trip_id = ?
        """, (trip_id,))
        
        rows = cursor.fetchall()
        
        participants = {}
        for row in rows:
            participants[row[0]] = {
                'display_name': row[1],
                'display_name_override': row[2]
            }
        
        conn.close()
        return participants
    
    def get_cached_expenses(self, trip_id):
        """Get cached expenses for a trip"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, paid_by_id, amount_cents, category, description, created_at
            FROM expenses
            WHERE trip_id = ?
            ORDER BY created_at DESC
        """, (trip_id,))
        
        rows = cursor.fetchall()
        
        expenses = []
        for row in rows:
            expense_id = row[0]
            
            # Get participants for this expense
            cursor.execute("""
                SELECT user_id, share_amount_cents
                FROM expense_participants
                WHERE expense_id = ?
            """, (expense_id,))
            
            participants = [
                {'user_id': p[0], 'share_amount_cents': p[1]}
                for p in cursor.fetchall()
            ]
            
            expenses.append({
                'id': expense_id,
                'paid_by_id': row[1],
                'amount_cents': row[2],
                'category': row[3],
                'description': row[4],
                'created_at': row[5],
                'expense_participants': participants
            })
        
        conn.close()
        return expenses
    
    # ==================== OFFLINE OPERATIONS ====================
    
    def add_offline_expense(self, trip_id, expense_data):
        """Add expense while offline (local only)"""
        import uuid
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        expense_id = f"offline_{uuid.uuid4()}"
        
        cursor.execute("""
            INSERT INTO expenses
            (id, trip_id, paid_by_id, amount_cents, category, description, created_at, synced, local_only)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1)
        """, (
            expense_id,
            trip_id,
            expense_data['paid_by_id'],
            expense_data['amount_cents'],
            expense_data.get('category', 'Other'),
            expense_data.get('description', ''),
            datetime.now().isoformat()
        ))
        
        # Add participants
        for participant in expense_data.get('participants', []):
            cursor.execute("""
                INSERT INTO expense_participants
                (expense_id, user_id, share_amount_cents, synced)
                VALUES (?, ?, ?, 0)
            """, (
                expense_id,
                participant['user_id'],
                participant['share_amount_cents']
            ))
        
        # Add to sync queue
        cursor.execute("""
            INSERT INTO sync_queue (action, table_name, data, created_at)
            VALUES ('CREATE', 'expenses', ?, ?)
        """, (
            json.dumps({**expense_data, 'id': expense_id, 'trip_id': trip_id}),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        return expense_id
    
    def get_sync_queue(self):
        """Get pending sync operations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, action, table_name, data
            FROM sync_queue
            ORDER BY id ASC
        """)
        
        queue = []
        for row in cursor.fetchall():
            queue.append({
                'id': row[0],
                'action': row[1],
                'table': row[2],
                'data': json.loads(row[3])
            })
        
        conn.close()
        return queue
    
    def remove_from_sync_queue(self, queue_id):
        """Remove item from sync queue after successful sync"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM sync_queue WHERE id = ?", (queue_id,))
        
        conn.commit()
        conn.close()
    
    def clear_cache(self):
        """Clear all cached data (logout/reset)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM trips")
        cursor.execute("DELETE FROM participants")
        cursor.execute("DELETE FROM expenses")
        cursor.execute("DELETE FROM expense_participants")
        cursor.execute("DELETE FROM settlements")
        cursor.execute("DELETE FROM sync_queue")
        
        conn.commit()
        conn.close()
    
    def get_cache_size(self):
        """Get size of cached data"""
        if os.path.exists(self.db_path):
            return os.path.getsize(self.db_path) / (1024 * 1024)  # MB
        return 0