const CACHE_NAME = 'gymbro-v5';
const ASSETS = [
  '/',
  '/log',
  '/history',
  '/ask',
  '/settings',
  '/timer',
  '/offline',
  '/static/index.css',
  '/static/logo.png',
  '/static/manifest.json',
  'https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap',
  'https://cdn.jsdelivr.net/npm/chart.js'
];

// Install: Cache everything immediately
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate: Cleanup old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)));
    })
  );
  self.clients.claim();
});

// Fetch: "Stale-While-Revalidate" Strategy
// 1. Show cached content immediately for speed
// 2. Fetch from network in background to update cache
// 3. If network fails and no cache, show /offline page
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.open(CACHE_NAME).then(cache => {
      return cache.match(event.request).then(cachedResponse => {
        const fetchedResponse = fetch(event.request).then(networkResponse => {
          cache.put(event.request, networkResponse.clone());
          return networkResponse;
        }).catch(() => {
            // If network fails and we have no cache, return the offline page
            if (!cachedResponse && event.request.mode === 'navigate') {
                return cache.match('/offline');
            }
        });

        return cachedResponse || fetchedResponse;
      });
    })
  );
});

// Background Sync
self.addEventListener('sync', event => {
  if (event.tag === 'sync-workouts') {
    console.log('Syncing data in background...');
  }
});

// Push
self.addEventListener('push', event => {
  const data = event.data ? event.data.text() : 'GymBro: Update!';
  event.waitUntil(
    self.registration.showNotification('GymBro', {
      body: data,
      icon: '/static/logo.png',
      badge: '/static/logo.png'
    })
  );
});
