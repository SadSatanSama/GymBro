const CACHE_NAME = 'gymbro-v135';
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
  
  event.respondWith(
    caches.match(event.request).then(response => {
      if (response) return response;

      return fetch(event.request).then(networkResponse => {
        if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return networkResponse;
      }).catch(err => {
        console.log('SW: Fetch failed, check if fallback available:', err);
        if (event.request.mode === 'navigate') {
            return caches.match('/');
        }
        return null;
      });
    })
  );
});
