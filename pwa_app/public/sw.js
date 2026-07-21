const BUILD_ID = self.location.search ? new URLSearchParams(self.location.search).get('v') : null;
const VER = BUILD_ID || '2';
const CACHE_NAME = `pwa-app-v${VER}`;
const STATIC_CACHE = `pwa-static-v${VER}`;
const API_CACHE = `pwa-api-v${VER}`;

const PRECACHE_URLS = [
    '/install/app',
    '/install/manifest',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE_URLS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => name !== STATIC_CACHE && name !== API_CACHE)
                    .map((name) => caches.delete(name))
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    if (event.request.method !== 'GET') return;

    // API calls - network first, fallback to cache
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(networkFirstWithTimeout(event.request, API_CACHE, 5000));
        return;
    }

    // Frappe assets - cache first
    if (url.pathname.startsWith('/assets/')) {
        event.respondWith(cacheFirst(event.request, STATIC_CACHE));
        return;
    }

    // App shell - network first
    if (url.pathname.startsWith('/install/app')) {
        event.respondWith(networkFirst(event.request, STATIC_CACHE));
        return;
    }

    // Default - network only
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});

async function cacheFirst(request, cacheName) {
    const cached = await caches.match(request);
    if (cached) return cached;
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        return new Response('Offline', { status: 503 });
    }
}

async function networkFirst(request, cacheName) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        const cached = await caches.match(request);
        if (cached) return cached;
        return new Response('Offline', { status: 503 });
    }
}

async function networkFirstWithTimeout(request, cacheName, timeoutMs) {
    const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('timeout')), timeoutMs)
    );
    try {
        const response = await Promise.race([fetch(request), timeoutPromise]);
        if (response.ok && response.status < 400) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        const cached = await caches.match(request);
        if (cached) return cached;
        return new Response(
            JSON.stringify({ message: 'You are offline', exc_type: 'OfflineError' }),
            { status: 503, headers: { 'Content-Type': 'application/json' } }
        );
    }
}

self.addEventListener('push', (event) => {
    let data = { title: 'Krystaa', body: 'New notification' };
    try { if (event.data) data = event.data.json(); } catch (e) { data = { title: 'Krystaa', body: event.data.text() }; }
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/assets/pwa_app/icons/icon-192.svg',
            badge: '/assets/pwa_app/icons/icon-192.svg',
            data: data.data || {},
        })
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const urlToOpen = event.notification.data?.url || '/install/app';
    event.waitUntil(
        clients.matchAll({ type: 'window' }).then((clientList) => {
            for (const client of clientList) {
                if (client.url === urlToOpen && 'focus' in client) return client.focus();
            }
            if (clients.openWindow) return clients.openWindow(urlToOpen);
        })
    );
});
