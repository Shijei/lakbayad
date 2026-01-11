// Service Worker Registration for Flet Apps
// Place this file in assets/ folder as sw-register.js

(function() {
  'use strict';
  
  console.log('[SW-Register] Checking for service worker support...');
  
  if (!('serviceWorker' in navigator)) {
    console.warn('[SW-Register] Service workers not supported');
    return;
  }
  
  // Register service worker when page loads
  window.addEventListener('load', function() {
    console.log('[SW-Register] Page loaded, registering service worker...');
    
    navigator.serviceWorker.register('/sw.js', {
      scope: '/'
    })
    .then(function(registration) {
      console.log('[SW-Register] ✓ Service worker registered!');
      console.log('[SW-Register] Scope:', registration.scope);
      
      // Check for updates
      registration.addEventListener('updatefound', function() {
        console.log('[SW-Register] Service worker update found!');
        const newWorker = registration.installing;
        
        newWorker.addEventListener('statechange', function() {
          console.log('[SW-Register] New worker state:', newWorker.state);
          if (newWorker.state === 'activated') {
            console.log('[SW-Register] New service worker activated!');
          }
        });
      });
      
      // Log current state
      if (registration.active) {
        console.log('[SW-Register] Active worker:', registration.active.state);
      }
      if (registration.waiting) {
        console.log('[SW-Register] Waiting worker:', registration.waiting.state);
      }
      if (registration.installing) {
        console.log('[SW-Register] Installing worker:', registration.installing.state);
      }
    })
    .catch(function(error) {
      console.error('[SW-Register] ✗ Registration failed:', error);
    });
  });
  
  // Log service worker controller
  navigator.serviceWorker.ready.then(function() {
    if (navigator.serviceWorker.controller) {
      console.log('[SW-Register] ✓ Page is controlled by service worker');
    } else {
      console.log('[SW-Register] Page is NOT controlled by service worker (refresh may be needed)');
    }
  });
})();