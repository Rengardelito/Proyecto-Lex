const CACHE_NAME = 'lexview-v1';

// Esto obliga al Service Worker a activarse apenas se instala
self.addEventListener('install', (event) => {
    self.skipWaiting();
});

// Esto hace que el Service Worker tome el control de la página inmediatamente
self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    // Necesario para que Chrome lo detecte como PWA
    event.respondWith(fetch(event.request));
});