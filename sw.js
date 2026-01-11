// Enhanced Service Worker for LakBayad
// Provides true offline support with IndexedDB caching

const CACHE_NAME = 'lakbayad-v2.1.0';
const DB_NAME = 'lakbayad-offline';
const DB_VERSION = 1;

// Assets to cache immediately
const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/assets/icon-192.png',
  '/assets/icon-512.png',
];

// ==================== IndexedDB Setup ====================

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      
      // Create object stores
      if (!db.objectStoreNames.contains('api-cache')) {
        db.createObjectStore('api-cache', { keyPath: 'url' });
      }
      
      if (!db.objectStoreNames.contains('offline-queue')) {
        const queueStore = db.createObjectStore('offline-queue', { keyPath: 'id', autoIncrement: true });
        queueStore.createIndex('timestamp', 'timestamp', { unique: false });
      }
    };
  });
}

async function getCachedResponse(url) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['api-cache'], 'readonly');
    const store = transaction.objectStore('api-cache');
    const request = store.get(url);
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function cacheResponse(url, data, timestamp) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['api-cache'], 'readwrite');
    const store = transaction.objectStore('api-cache');
    const request = store.put({ url, data, timestamp });
    
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function queueOfflineAction(action) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['offline-queue'], 'readwrite');
    const store = transaction.objectStore('offline-queue');
    const request = store.add({
      ...action,
      timestamp: Date.now()
    });
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getOfflineQueue() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['offline-queue'], 'readonly');
    const store = transaction.objectStore('offline-queue');
    const request = store.getAll();
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function removeFromQueue(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['offline-queue'], 'readwrite');
    const store = transaction.objectStore('offline-queue');
    const request = store.delete(id);
    
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

// ==================== Service Worker Events ====================

self.addEventListener('install', (event) => {
  console.log('[SW] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching static assets');
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Activating...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Only handle same-origin requests and Supabase API
  if (url.origin !== location.origin && !url.hostname.includes('supabase.co')) {
    return;
  }
  
  // Handle API requests specially
  if (url.pathname.startsWith('/rest/v1/') || url.hostname.includes('supabase.co')) {
    event.respondWith(handleApiRequest(request));
  } else {
    // Static assets - cache first
    event.respondWith(handleStaticRequest(request));
  }
});

async function handleStaticRequest(request) {
  // Try cache first, then network
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    // Cache successful responses
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('[SW] Network failed, no cache available:', error);
    throw error;
  }
}

async function handleApiRequest(request) {
  const url = request.url;
  const method = request.method;
  
  // GET requests - cache strategy
  if (method === 'GET') {
    try {
      // Try network first
      const networkResponse = await fetch(request);
      
      if (networkResponse.ok) {
        // Cache the response
        const data = await networkResponse.clone().json();
        await cacheResponse(url, data, Date.now());
      }
      
      return networkResponse;
    } catch (error) {
      console.log('[SW] Network failed, trying cache for:', url);
      
      // Network failed - try cache
      const cached = await getCachedResponse(url);
      if (cached && cached.data) {
        console.log('[SW] Returning cached data for:', url);
        return new Response(JSON.stringify(cached.data), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
      }
      
      throw error;
    }
  }
  
  // POST/PATCH/DELETE - queue if offline
  if (method === 'POST' || method === 'PATCH' || method === 'DELETE') {
    try {
      // Try network first
      const networkResponse = await fetch(request);
      return networkResponse;
    } catch (error) {
      console.log('[SW] Network failed, queueing action:', method, url);
      
      // Queue for later sync
      const body = request.method !== 'GET' ? await request.clone().text() : null;
      await queueOfflineAction({
        method,
        url,
        headers: Object.fromEntries(request.headers.entries()),
        body
      });
      
      // Return success response so app doesn't break
      return new Response(JSON.stringify({
        success: true,
        offline: true,
        message: 'Saved locally, will sync when online'
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
        });
    }
  }
  
  // Default - just try to fetch
  return fetch(request);
}

// ==================== Background Sync ====================

self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-offline-queue') {
    console.log('[SW] Background sync triggered');
    event.waitUntil(syncOfflineQueue());
  }
});

async function syncOfflineQueue() {
  const queue = await getOfflineQueue();
  console.log('[SW] Syncing', queue.length, 'offline actions');
  
  for (const action of queue) {
    try {
      const response = await fetch(action.url, {
        method: action.method,
        headers: action.headers,
        body: action.body
      });
      
      if (response.ok) {
        console.log('[SW] Synced:', action.method, action.url);
        await removeFromQueue(action.id);
      } else {
        console.log('[SW] Sync failed:', response.status);
      }
    } catch (error) {
      console.log('[SW] Sync error:', error);
      // Keep in queue for next sync
    }
  }
  
  // Notify clients that sync is complete
  const clients = await self.clients.matchAll();
  clients.forEach(client => {
    client.postMessage({
      type: 'SYNC_COMPLETE',
      synced: queue.length
    });
  });
}

// ==================== Message Handling ====================

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'SYNC_NOW') {
    syncOfflineQueue();
  }
  
  if (event.data && event.data.type === 'GET_QUEUE_SIZE') {
    getOfflineQueue().then(queue => {
      event.ports[0].postMessage({ size: queue.length });
    });
  }
});

console.log('[SW] Service Worker loaded');