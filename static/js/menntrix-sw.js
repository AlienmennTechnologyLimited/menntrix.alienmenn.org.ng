// ============================================================
// MENNTRIX SERVICE WORKER
// Handles Web Push notifications + click-to-open
// ============================================================

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
    let data = {};
    try { data = event.data ? event.data.json() : {}; } catch (e) {}

    const title = data.title || 'MENNTRIX';
    const options = {
        body: data.body || '',
        icon: data.icon || '/static/images/logo.gif',
        badge: '/static/images/logo.gif',
        data: { url: data.url || '/dashboard/' },
        tag: data.tag || 'menntrix-notification',
    };

    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const url = (event.notification.data && event.notification.data.url) || '/dashboard/';
    const fullUrl = url.startsWith('http') ? url : location.origin + url;

    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
            for (const client of clients) {
                if (client.url.startsWith(location.origin) && 'focus' in client) {
                    client.navigate(fullUrl);
                    return client.focus();
                }
            }
            if (self.clients.openWindow) {
                return self.clients.openWindow(fullUrl);
            }
        })
    );
});