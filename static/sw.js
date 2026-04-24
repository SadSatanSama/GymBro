const CACHE_NAME = 'gymbro-v6';
const ASSETS = [
  '/',
  '/log',
  '/history',
  '/ask',
  '/settings',
  '/timer',
  '/offline',
  '/static/index.css',
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

// Fetch: Smart Strategy
// - Navigation (Pages): Network-First (Show latest data if online)
// - Assets (CSS/JS): Stale-While-Revalidate (Load fast, update background)
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Strategy for Navigation (HTML Pages)
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then(networkResponse => {
          return caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
          });
        })
        .catch(() => {
          return caches.match(event.request) || caches.match('/offline');
        })
    );
    return;
  }

  // Strategy for Assets (CSS, JS, Fonts)
  event.respondWith(
    caches.open(CACHE_NAME).then(cache => {
      return cache.match(event.request).then(cachedResponse => {
        const fetchedResponse = fetch(event.request).then(networkResponse => {
          cache.put(event.request, networkResponse.clone());
          return networkResponse;
        }).catch(() => {
           // Silent fail for non-critical assets
        });
        return cachedResponse || fetchedResponse;
      });
    })
  );
});
