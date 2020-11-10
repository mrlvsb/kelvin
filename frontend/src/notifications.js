import { writable } from 'svelte/store'
import { fetch } from './api.js'

export const notifications = (function () {
  const { subscribe, set } = writable(null);

  async function refresh() {
    const res = await fetch('/notification/all');
    set(await res.json());
  }

  refresh();

  return {
    subscribe,
    markRead: async (id) => {
      const res = await fetch('/notification/mark_as_read/' + id, { method: 'POST' });
      set(await res.json());
    },
    markAllRead: async () => {
      const res = await fetch('/notification/mark_as_read', { method: 'POST' });
      set(await res.json());
    }
  }
})();


export const pushNotifications = (function () {
  const { subscribe, set, update } = writable({
    supported: false,
    enabled: null,
  });

  function getPublicKey() {
    return document.querySelector('meta[name="django-webpush-vapid-key"]').content;
  }

  function urlB64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
      .replace(/\-/g, '+')
      .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (var i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  const subscribeOpts = {
    userVisibleOnly: true,
    applicationServerKey: urlB64ToUint8Array(getPublicKey()),
  };

  async function getSubscription() {
    if(!reg) {
      return null;
    }

    try {
      let sub = await reg.pushManager.getSubscription();
      if (sub) {
        return sub;  
      }

      sub = await reg.pushManager.subscribe(subscribeOpts);

      const browser = navigator.userAgent.match(/(firefox|msie|chrome|safari|trident)/ig)[0].toLowerCase();
      const data = {
        status_type: 'subscribe',
        subscription: sub.toJSON(),
        browser: browser,
        group: null,
      };

      await fetch('/webpush/save_information', {
        method: 'post',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      return sub;
    } catch(exception) {
      console.log(exception);
    }

    return null;
  }

  async function subscribePushNotifications() {
    const isEnabled = await getSubscription() !== null;
    update(s => {
      s.enabled = isEnabled;
      return s;
    });
    return isEnabled;
  }

  let reg = null;
  if ('serviceWorker' in navigator && 'PushManager' in window && getPublicKey()) {
    (async() => {
      reg = await navigator.serviceWorker.register('/static/service-worker.js');
      if (!(reg.showNotification)) {
        return;
      }
      update(s => {
        s.supported = true;
        return s;
      });
      subscribePushNotifications();
    })();
  }

  return {
    subscribe,
    subscribePushNotifications,
  }
})();