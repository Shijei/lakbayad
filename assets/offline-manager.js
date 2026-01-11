// Offline Manager for LakBayad
// Detects online/offline status and shows visual indicator

class OfflineManager {
  constructor() {
    this.isOnline = navigator.onLine;
    this.indicator = null;
    this.queueSize = 0;
    
    this.init();
  }
  
  init() {
    // Listen for online/offline events
    window.addEventListener('online', () => this.handleOnline());
    window.addEventListener('offline', () => this.handleOffline());
    
    // Listen for service worker messages
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data.type === 'SYNC_COMPLETE') {
          console.log('[OfflineManager] Sync complete:', event.data.synced, 'items');
          this.queueSize = 0;
          this.updateIndicator();
        }
      });
      
      // Check queue size periodically
      setInterval(() => this.checkQueueSize(), 5000);
    }
    
    // Create indicator
    this.createIndicator();
    this.updateIndicator();
  }
  
  createIndicator() {
    // Check if indicator already exists
    if (document.getElementById('offline-indicator')) {
      this.indicator = document.getElementById('offline-indicator');
      return;
    }
    
    // Create indicator element
    this.indicator = document.createElement('div');
    this.indicator.id = 'offline-indicator';
    this.indicator.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      z-index: 9999;
      padding: 8px 16px;
      text-align: center;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 14px;
      font-weight: 500;
      display: none;
      animation: slideDown 0.3s ease-out;
    `;
    
    document.body.appendChild(this.indicator);
  }
  
  updateIndicator() {
    if (!this.indicator) return;
    
    if (this.isOnline && this.queueSize === 0) {
      // Online and synced - hide indicator
      this.indicator.style.display = 'none';
    } else if (this.isOnline && this.queueSize > 0) {
      // Online but syncing
      this.indicator.style.display = 'block';
      this.indicator.style.backgroundColor = '#FFF3CD';
      this.indicator.style.color = '#856404';
      this.indicator.innerHTML = `
        <span>⏳ Syncing ${this.queueSize} offline ${this.queueSize === 1 ? 'change' : 'changes'}...</span>
      `;
    } else {
      // Offline
      this.indicator.style.display = 'block';
      this.indicator.style.backgroundColor = '#F8D7DA';
      this.indicator.style.color = '#721C24';
      
      let message = '📵 Offline Mode - Changes will sync when back online';
      if (this.queueSize > 0) {
        message += ` (${this.queueSize} pending)`;
      }
      
      this.indicator.innerHTML = `<span>${message}</span>`;
    }
  }
  
  handleOnline() {
    console.log('[OfflineManager] Back online!');
    this.isOnline = true;
    this.updateIndicator();
    
    // Trigger sync
    if ('serviceWorker' in navigator && 'sync' in registration) {
      navigator.serviceWorker.ready.then((registration) => {
        registration.sync.register('sync-offline-queue');
      });
    } else {
      // Manual sync fallback
      this.manualSync();
    }
  }
  
  handleOffline() {
    console.log('[OfflineManager] Gone offline');
    this.isOnline = false;
    this.updateIndicator();
  }
  
  async checkQueueSize() {
    if (!('serviceWorker' in navigator)) return;
    
    try {
      const registration = await navigator.serviceWorker.ready;
      const messageChannel = new MessageChannel();
      
      messageChannel.port1.onmessage = (event) => {
        if (event.data && event.data.size !== undefined) {
          this.queueSize = event.data.size;
          this.updateIndicator();
        }
      };
      
      registration.active.postMessage(
        { type: 'GET_QUEUE_SIZE' },
        [messageChannel.port2]
      );
    } catch (error) {
      console.error('[OfflineManager] Error checking queue:', error);
    }
  }
  
  async manualSync() {
    if (!('serviceWorker' in navigator)) return;
    
    try {
      const registration = await navigator.serviceWorker.ready;
      registration.active.postMessage({ type: 'SYNC_NOW' });
    } catch (error) {
      console.error('[OfflineManager] Error triggering sync:', error);
    }
  }
}

// Initialize offline manager when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.offlineManager = new OfflineManager();
  });
} else {
  window.offlineManager = new OfflineManager();
}

// Add CSS animation
const style = document.createElement('style');
style.textContent = `
  @keyframes slideDown {
    from {
      transform: translateY(-100%);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
`;
document.head.appendChild(style);

console.log('[OfflineManager] Initialized');