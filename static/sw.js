// DocuReminder Service Worker — handles background push notifications
self.addEventListener('push', function(event) {
  let data = { title: '🗂️ DocuReminder', body: 'Ada dokumen yang perlu perhatian!', url: '/' };
  try { data = Object.assign(data, JSON.parse(event.data.text())); } catch(e) {}

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/static/icon.png',
      badge: '/static/icon.png',
      data: { url: data.url },
      actions: [{ action: 'open', title: 'Buka App' }],
      requireInteraction: true,
    })
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(clients.openWindow(url));
});
