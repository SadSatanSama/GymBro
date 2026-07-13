const CACHE_NAME = 'gymbro-v142';
const OFFLINE_URL = '/static/offline.html';

const ASSETS = [
  '/',
  OFFLINE_URL,
  '/static/index.css',
  '/static/logo.png',
  '/static/logo-192.png',
  '/static/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      for (const asset of ASSETS) {
        try {
          await cache.add(asset);
        } catch (e) {
          console.warn('SW: Failed to cache on install:', asset, e);
        }
      }
    })()
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    (async () => {
      if ('navigationPreload' in self.registration) {
        await self.registration.navigationPreload.enable();
      }
      const keys = await caches.keys();
      await Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })()
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  if (event.request.url.includes('githubusercontent.com')) return;

  if (event.request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const preloadResponse = await event.preloadResponse;
          if (preloadResponse) {
            return preloadResponse;
          }
          const networkResponse = await fetch(event.request);
          // Update cache with fresh navigation response
          if (networkResponse && networkResponse.status === 200) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        } catch (error) {
          const cache = await caches.open(CACHE_NAME);
          // First try matching the exact navigated page in cache (e.g., homepage '/')
          const cachedPage = await cache.match(event.request, { ignoreSearch: true });
          if (cachedPage) return cachedPage;
          // Fallback to cached root
          const cachedRoot = await cache.match('/', { ignoreSearch: true });
          if (cachedRoot) return cachedRoot;
          // Finally fallback to dedicated offline HTML
          const offlinePage = await cache.match(OFFLINE_URL);
          if (offlinePage) return offlinePage;
          return new Response('Offline', { status: 200, headers: { 'Content-Type': 'text/plain' } });
        }
      })()
    );
    return;
  }

  event.respondWith(
    caches.match(event.request, { ignoreSearch: true }).then(cached => {
      return cached || fetch(event.request).then(response => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => {
        return new Response('', { status: 200 });
      });
    })
  );
});
