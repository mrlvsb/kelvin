import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Notifications from './Notifications.vue';
import { mockFetch } from '../utilities/test';
import { Notification } from '../utilities/notifications';

const exampleNotifications = [
    {
        id: 1,
        action_object: 'some-action-object',
        action_object_url: 'some-action-object-url',
        actor: 'some-actor1',
        actor_content_type: 1,
        actor_object_id: 'some-actor-object-id',
        custom_text: 'some-custom-text',
        deleted: false,
        description: 'some-description',
        emailed: false,
        important: false,
        level: 'info',
        public: false,
        recepient: 1,
        timestamp: '0',
        unread: false,
        verb: 'some-verb'
    },
    {
        id: 2,
        action_object: 'some-action-object',
        action_object_url: 'some-action-object-url2',
        actor: 'some-actor2',
        actor_content_type: 1,
        actor_object_id: 'some-actor-object-id2',
        custom_text: 'some-custom-text2',
        deleted: false,
        description: 'some-description2',
        emailed: false,
        important: false,
        level: 'info',
        public: false,
        recepient: 1,
        timestamp: '0',
        unread: false,
        verb: 'some-verb'
    }
] satisfies Notification[];

beforeEach(() => {
    // Mock the current date to make tests deterministic
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2025-01-01T00:00:00.000Z'));

    //fake csrf token
    const csrf = document.createElement('meta');
    csrf.name = 'csrf-token';
    csrf.content = 'some-token';
    document.head.appendChild(csrf);

    //fake vapid key
    const vapid = document.createElement('meta');
    vapid.name = 'django-webpush-vapid-key';
    vapid.content = 'some-key';
    document.head.appendChild(vapid);

    mockFetch({
        '/notification/all': {
            okStatus: true,
            data: {
                notifications: exampleNotifications
            }
        },
        '/notification/mark_as_read/1': {
            okStatus: true,
            data: {
                notifications: exampleNotifications.slice(1)
            }
        }
    });
});

afterEach(() => {
    vi.useRealTimers();

    document.querySelectorAll("meta[name='csrf-token']").forEach((e) => e.remove());
    document.querySelectorAll("meta[name='django-webpush-vapid-key']").forEach((e) => e.remove());

    vi.restoreAllMocks();
});

describe('Notifications', () => {
    it("Don't wait for notifications", () => {
        const wrapper = mount(Notifications);

        expect(wrapper.html()).toMatchSnapshot();
    });
    it('Wait for notification', async () => {
        const wrapper = mount(Notifications);

        await vi.waitFor(() => expect(wrapper.html()).toContain('some-actor1'));
        expect(wrapper.html()).toMatchSnapshot();
    });
    it('Read notification', async () => {
        const fetchSpy = vi.spyOn(globalThis, 'fetch');

        const wrapper = mount(Notifications);

        await vi.waitFor(() => expect(wrapper.html()).toContain('some-actor1'));

        await wrapper.find('.btn-close').trigger('click');

        await vi.waitFor(() => expect(wrapper.html()).not.toContain('some-actor1'));

        expect(fetchSpy).toBeCalledWith(
            '/notification/mark_as_read/' + exampleNotifications[0].id,
            expect.anything()
        );

        expect(wrapper.html()).toMatchSnapshot();
    });
});
