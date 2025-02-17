import { getDataWithCSRF } from './api';

//@TODO: complete null unions if missing
export type Notification = {
    id: number;
    level: 'info'; //@TODO: add other levels
    recepient: number;
    unread: boolean;
    actor_content_type: number;
    actor_object_id: string;
    verb: string;
    description: string | null;
    timestamp: string;
    public: boolean;
    deleted: boolean;
    emailed: boolean;
    important: boolean;
    actor: string;
    action_object: string;
    action_object_url: string;
    custom_text?: string;
    target?: string;
};

export const getNotifications = async () => {
    const data = await getDataWithCSRF<{ notifications: Notification[] }>('/notification/all');
    return data.notifications;
};

export const markRead = async (id: number) => {
    const data = await getDataWithCSRF<{ notifications: Notification[] }>(
        '/notification/mark_as_read/' + id,
        'POST'
    );
    return data.notifications;
};

export const markAllRead = async () => {
    const data = await getDataWithCSRF<{ notifications: Notification[] }>(
        '/notification/mark_as_read',
        'POST'
    );
    return data.notifications;
};

const getPublicKey = () => {
    return document.querySelector<HTMLMetaElement>('meta[name="django-webpush-vapid-key"]').content;
};

const urlB64ToUint8Array = (base64String: string) => {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
};

const getSubscription = async (reg: ServiceWorkerRegistration) => {
    const subscribeOpts = {
        userVisibleOnly: true,
        applicationServerKey: urlB64ToUint8Array(getPublicKey())
    };

    try {
        let sub = await reg.pushManager.getSubscription();
        if (sub) {
            return sub;
        }

        sub = await reg.pushManager.subscribe(subscribeOpts);

        const browser = navigator.userAgent
            .match(/(firefox|msie|chrome|safari|trident)/gi)[0]
            .toLowerCase();
        const data = {
            status_type: 'subscribe',
            subscription: sub.toJSON(),
            browser: browser,
            group: null
        };

        await getDataWithCSRF('/webpush/save_information', 'POST', data, {
            'Content-Type': 'application/json'
        });
        return sub;
    } catch (exception) {
        console.log(exception);
    }

    return null;
};

export const subscribePushNotifications = async (reg: ServiceWorkerRegistration) => {
    const isEnabled = (await getSubscription(reg)) !== null;
    return isEnabled;
};

export type PushNotifications =
    | {
          supported: true;
          enabled: boolean;
          reg: ServiceWorkerRegistration;
      }
    | {
          supported: false;
          enabled: null;
          reg: null;
      };

export const getPushStatus = async (): Promise<PushNotifications> => {
    let reg: null | ServiceWorkerRegistration = null;
    if ('serviceWorker' in navigator && 'PushManager' in window && getPublicKey()) {
        try {
            reg = await navigator.serviceWorker.register('/static/service-worker.js');
            if (!reg.showNotification) {
                return;
            }
            return {
                supported: true,
                enabled: await subscribePushNotifications(reg),
                reg
            };
        } catch (err) {
            console.log(err);
            return {
                supported: true,
                enabled: false,
                reg
            };
        }
    }

    return {
        supported: false,
        enabled: null,
        reg: null
    };
};
