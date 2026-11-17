// Laundrix service worker: makes the app installable and shows a friendly page offline.
// It never caches /api/ data or logged-in pages (customer data stays private).
const V = 'laundrix-v3';
const SHELL = ['/offline', '/static/css/layout.css', '/static/css/app.css', '/static/js/app.js', '/static/js/customer.js', '/static/icons/icon-192.png'];

self.addEventListener('install', e => e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())));

self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/api/')) return;
  if (u.pathname.startsWith('/static/')) {            // network first, cache as backup
    e.respondWith(fetch(r).then(res => { const copy = res.clone(); caches.open(V).then(c => c.put(r, copy)); return res; })
      .catch(() => caches.match(r)));
  } else if (r.mode === 'navigate') {                  // pages: network only, offline page if it fails
    e.respondWith(fetch(r).catch(() => caches.match('/offline')));
  }
});
