"""
Hybrid Database - Tries online first, falls back to offline cache
"""
from offline_db import OfflineDB

class HybridDatabase:
    """
    Smart database that:
    1. Tries online (Supabase) first
    2. Caches responses locally
    3. Falls back to cache if offline
    4. Queues changes for sync
    """
    
    def __init__(self, online_db, offline_db):
        self.online = online_db  # Your existing database.py
        self.offline = offline_db  # New OfflineDB
        self.is_online = True  # Assume online by default
    
    def _check_connection(self):
        """
        Simplified check - just assume online
        We'll detect offline through actual request failures
        """
        # Don't block with network checks - just return current state
        return self.is_online
    
    # ==================== SMART METHODS ====================
    
    def get_user_trips(self, user_id):
        """Get trips - online preferred, offline fallback"""
        self._check_connection()
        
        print(f"[DEBUG] get_user_trips: is_online={self.is_online}, user_id={user_id}")
        
        if self.is_online:
            try:
                print(f"[DEBUG] Attempting online request...")
                response = self.online.get_user_trips(user_id)
                print(f"[DEBUG] Online response: {response.data if hasattr(response, 'data') else 'NO DATA ATTR'}")
                
                # Cache trips for offline use
                if response.data:
                    print(f"[DEBUG] Caching {len(response.data)} trips")
                    for trip_wrapper in response.data:
                        # Handle nested structure: {'trips': {...}}
                        trip = trip_wrapper.get('trips') if 'trips' in trip_wrapper else trip_wrapper
                        print(f"[DEBUG] Caching trip: {trip.get('id', 'NO ID')} - {trip.get('name', 'NO NAME')}")
                        self.offline.cache_trip(trip)
                else:
                    print("[DEBUG] No trips to cache")
                
                return response
            except Exception as e:
                # Online failed, use cache
                print(f"[DEBUG] Online request FAILED: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                self.is_online = False
                print(f"[DEBUG] Marked as offline, falling through to cache...")
        
        # Offline mode
        print("[DEBUG] === USING OFFLINE MODE ===")
        print(f"[DEBUG] Loading cached trips for user: {user_id}")
        cached_trips = self.offline.get_cached_trips()
        print(f"[DEBUG] Found {len(cached_trips)} cached trips")
        print(f"[DEBUG] Cached trip IDs: {list(cached_trips.keys())}")
        
        # Return in the same nested format as online
        cached_data = []
        for trip_id, trip in cached_trips.items():
            print(f"[DEBUG] Preparing cached trip: {trip_id} - {trip.get('name', 'NO NAME')}")
            cached_data.append({'trips': trip})
        
        print(f"[DEBUG] Returning {len(cached_data)} trips from cache")
        result = type('Response', (), {'data': cached_data})()
        print(f"[DEBUG] Result data: {result.data}")
        return result
    
    def get_trip_participants(self, trip_id):
        """Get participants - online preferred, offline fallback"""
        self._check_connection()
        
        if self.is_online:
            try:
                response = self.online.get_trip_participants(trip_id)
                
                # Cache participants
                if response.data:
                    participants = {}
                    for p in response.data:
                        participants[p['user_id']] = p
                    self.offline.cache_participants(trip_id, participants)
                
                return response
            except:
                self.is_online = False
        
        # Offline mode
        cached_participants = self.offline.get_cached_participants(trip_id)
        return type('Response', (), {'data': list(cached_participants.values())})()
    
    def get_trip_expenses(self, trip_id):
        """Get expenses - online preferred, offline fallback"""
        self._check_connection()
        
        if self.is_online:
            try:
                response = self.online.get_trip_expenses(trip_id)
                
                # Cache expenses
                if response.data:
                    for expense in response.data:
                        self.offline.cache_expense(expense)
                
                return response
            except:
                self.is_online = False
        
        # Offline mode
        cached_expenses = self.offline.get_cached_expenses(trip_id)
        return type('Response', (), {'data': cached_expenses})()
    
    def create_expense(self, trip_id, paid_by_id, amount_cents, category, description):
        """Create expense - queue if offline"""
        self._check_connection()
        
        expense_data = {
            'paid_by_id': paid_by_id,
            'amount_cents': amount_cents,
            'category': category,
            'description': description
        }
        
        if self.is_online:
            try:
                # Try online first
                response = self.online.create_expense(trip_id, paid_by_id, amount_cents, category, description)
                
                # Cache the created expense
                if response.data and len(response.data) > 0:
                    self.offline.cache_expense(response.data[0])
                
                return response
            except:
                self.is_online = False
        
        # Offline mode - add to local database and sync queue
        expense_id = self.offline.add_offline_expense(trip_id, expense_data)
        
        return type('Response', (), {'data': [{'id': expense_id, **expense_data}]})()
    
    def sync_offline_changes(self):
        """Sync all offline changes to server"""
        self._check_connection()
        
        if not self.is_online:
            return {'success': False, 'message': 'Still offline'}
        
        queue = self.offline.get_sync_queue()
        synced = 0
        errors = []
        
        for item in queue:
            try:
                if item['table'] == 'expenses':
                    data = item['data']
                    response = self.online.create_expense(
                        data['trip_id'],
                        data['paid_by_id'],
                        data['amount_cents'],
                        data['category'],
                        data['description']
                    )
                    
                    if response.data:
                        # Success - remove from queue
                        self.offline.remove_from_sync_queue(item['id'])
                        synced += 1
            except Exception as e:
                errors.append(str(e))
        
        return {
            'success': True,
            'synced': synced,
            'errors': errors
        }
    
    def get_connection_status(self):
        """Get current connection status"""
        self._check_connection()
        
        queue_size = len(self.offline.get_sync_queue())
        cache_size = self.offline.get_cache_size()
        
        return {
            'online': self.is_online,
            'pending_sync': queue_size,
            'cache_size_mb': round(cache_size, 2)
        }
    
    # ==================== PASSTHROUGH METHODS ====================
    # All other methods pass directly to online database
    
    def __getattr__(self, name):
        """
        Pass through any method calls that aren't explicitly defined
        This allows HybridDatabase to work as a drop-in replacement
        
        IMPORTANT: Pass through database methods (including private ones),
        but not Python magic methods (like __dict__, __class__, etc.)
        """
        # Only block double-underscore magic methods
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        
        # Pass through everything else to online database
        # This includes:
        # - Public methods: get_user_by_email()
        # - Private methods: _request()
        # - Properties: any attributes
        return getattr(self.online, name)