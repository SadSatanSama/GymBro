const CACHE_NAME = 'gymbro-v3';
const ASSETS = [
  '/',
  '/log',
  '/history',
  '/ask',
  '/settings',
  '/static/index.css',
  '/static/logo.png',
  '/static/manifest.json',
  'https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap',
  'https://cdn.jsdelivr.net/npm/chart.js'
];

// Install Event
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('Caching all assets for elite offline experience');
      return cache.addAll(ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate Event
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)));
    })
  );
  self.clients.claim();
});

// Fetch Event (Network First, fallback to Cache)
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// Background Sync Hook
self.addEventListener('sync', event => {
  if (event.tag === 'sync-workouts') {
    console.log('OS-level Background Sync triggered');
    // Our app handles this via syncQueue in the UI, but we keep the hook for Store compatibility
  }
});

// Periodic Sync Hook
self.addEventListener('periodicsync', event => {
  if (event.tag === 'update-cache') {
    console.log('Periodic Background Sync: Updating assets...');
  }
});

// Push Notification Hook
self.addEventListener('push', event => {
  const data = event.data ? event.data.text() : 'Time for your workout!';
  event.waitUntil(
    self.registration.showNotification('GymBro', {
      body: data,
      icon: '/static/logo.png',
      badge: '/static/logo.png'
    })
  );
});
