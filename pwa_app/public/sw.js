const CACHE_NAME = 'pwa-app-v1';
const STATIC_CACHE = 'pwa-static-v1';
const API_CACHE = 'pwa-api-v1';

// Assets to pre-cache on install
const PRECACHE_URLS = [
	'/install/app',
	'/assets/pwa_app/manifest.json',
];

// Install event - pre-cache core assets
self.addEventListener('install', (event) => {
	event.waitUntil(
		caches.open(STATIC_CACHE).then((cache) => {
			return cache.addAll(PRECACHE_URLS);
		})
	);
	self.skipWaiting();
});

// Activate event - clean old caches
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

// Fetch event strategy
self.addEventListener('fetch', (event) => {
	const url = new URL(event.request.url);

	// Skip non-GET requests
	if (event.request.method !== 'GET') return;

	// API calls - network first, fallback to cache
	if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/api/method/')) {
		event.respondWith(networkFirstWithTimeout(event.request, API_CACHE, 5000));
		return;
	}

	// Frappe assets - cache first
	if (url.pathname.startsWith('/assets/')) {
		event.respondWith(cacheFirst(event.request, STATIC_CACHE));
		return;
	}

	// App shell (HTML navigation) - network first
	if (url.pathname.startsWith('/install/app')) {
		event.respondWith(networkFirst(event.request, STATIC_CACHE));
		return;
	}

	// Default - network only
	event.respondWith(fetch(event.request).catch(() => {
		return caches.match(event.request);
	}));
});

// Cache-first strategy
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

// Network-first strategy
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

// Network-first with timeout
async function networkFirstWithTimeout(request, cacheName, timeoutMs) {
	const timeoutPromise = new Promise((_, reject) =>
		setTimeout(() => reject(new Error('timeout')), timeoutMs)
	);

	try {
		const response = await Promise.race([
			fetch(request),
			timeoutPromise,
		]);
		if (response.ok && response.status < 400) {
			const cache = await caches.open(cacheName);
			cache.put(request, response.clone());
		}
		return response;
	} catch (error) {
		const cached = await caches.match(request);
		if (cached) return cached;
		// Return a JSON response for API calls
		return new Response(
			JSON.stringify({ message: 'You are offline', exc_type: 'OfflineError' }),
			{ status: 503, headers: { 'Content-Type': 'application/json' } }
		);
	}
}

// Push notification event
self.addEventListener('push', (event) => {
	let data = { title: 'PWA App', body: 'New notification' };
	try {
		if (event.data) {
			data = event.data.json();
		}
	} catch (e) {
		data = { title: 'PWA App', body: event.data.text() };
	}

	const options = {
		body: data.body,
		icon: '/assets/pwa_app/icons/icon-192.png',
		badge: '/assets/pwa_app/icons/icon-192.png',
		data: data.data || {},
	};

	event.waitUntil(
		self.registration.showNotification(data.title, options)
	);
});

// Notification click event
self.addEventListener('notificationclick', (event) => {
	event.notification.close();
	const urlToOpen = event.notification.data?.url || '/install/app';

	event.waitUntil(
		clients.matchAll({ type: 'window' }).then((clientList) => {
			for (const client of clientList) {
				if (client.url === urlToOpen && 'focus' in client) {
					return client.focus();
				}
			}
			if (clients.openWindow) {
				return clients.openWindow(urlToOpen);
			}
		})
	);
});
