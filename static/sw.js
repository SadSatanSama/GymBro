const CACHE_NAME = 'gymbro-v138';
const ASSETS = [
  '/',
  '/static/index.css',
  '/static/logo.png',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('SW: Pre-caching assets');
        return cache.addAll(ASSETS);
      })
      .catch(err => console.error('SW: Install pre-cache failed:', err))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(key => key !== CACHE_NAME)
            .map(key => {
              console.log('SW: Removing old cache', key);
              return caches.delete(key);
            })
      );
    }).catch(err => console.error('SW: Activation failed:', err))
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  
  // Skip caching for external GitHub DB to prevent "poisoned" cache
  if (event.request.url.includes('githubusercontent.com')) {
      return;
  }

  event.respondWith(
    caches.match(event.request).then(response => {
      if (response) return response;

      return fetch(event.request).then(networkResponse => {
        if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return networkResponse;
      }).catch(async err => {
        console.log('SW: Fetch failed, check if fallback available:', err);
        if (event.request.mode === 'navigate') {
            const cachedRoot = await caches.match('/');
            if (cachedRoot) return cachedRoot;
            return new Response(
              '<!DOCTYPE html><html><head><title>Offline - GymBro</title><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="background:#0b0f19;color:#fff;font-family:sans-serif;text-align:center;padding:2rem;"><h1>GymBro Offline</h1><p>Unable to connect to server. Please check your internet connection or try again shortly.</p><button onclick="location.reload()" style="padding:0.75rem 1.5rem;border-radius:12px;background:#6366f1;color:#fff;border:none;font-weight:bold;cursor:pointer;margin-top:1rem;">Retry</button></body></html>',
              { headers: { 'Content-Type': 'text/html' }, status: 503 }
            );
        }
        return new Response('', { status: 408, statusText: 'Request timed out.' });
      });
    })
  );
});
