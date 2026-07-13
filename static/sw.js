const CACHE_NAME = 'gymbro-v140';
const ASSETS = [
  '/',
  '/static/index.css',
  '/static/logo.png',
  '/static/logo-192.png',
  '/static/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      await cache.addAll(ASSETS);
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
          return networkResponse;
        } catch (error) {
          const cache = await caches.open(CACHE_NAME);
          const cachedResponse = await cache.match('/', { ignoreSearch: true });
          if (cachedResponse) {
            return cachedResponse;
          }
          return new Response(
            '<!DOCTYPE html><html><head><title>Offline - GymBro</title><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="background:#0b0f19;color:#fff;font-family:sans-serif;text-align:center;padding:2rem;"><h1>GymBro Offline</h1><p>Unable to connect to server. Please check your internet connection or try again shortly.</p><button onclick="location.reload()" style="padding:0.75rem 1.5rem;border-radius:12px;background:#6366f1;color:#fff;border:none;font-weight:bold;cursor:pointer;margin-top:1rem;">Retry</button></body></html>',
            { headers: { 'Content-Type': 'text/html' }, status: 200 }
          );
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
