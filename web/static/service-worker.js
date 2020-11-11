self.addEventListener('push', (event) => {
  if(!event.data) {
    return;
  }

  let data = JSON.parse(event.data.text());
  event.waitUntil(
    self.registration.showNotification(data.head, data)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  if(event.notification.data) {
    if(event.notification.data.notification_id) {
      fetch('/notification/mark_as_read/' + event.notification.data.notification_id, { method: 'POST' });
    }

    if(event.notification.data.url) {
      event.waitUntil(
        clients.openWindow(event.notification.data.url)
      );
    }
  }
});
