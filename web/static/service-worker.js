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
  if(event.notification.data && event.notification.data.url) {
    event.waitUntil(
      clients.openWindow(event.notification.data.url)
    );  
  }
});
