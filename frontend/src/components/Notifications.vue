<script setup lang="ts">
import {
  notifications,
  pushNotifications,
  importantNotificationsCount,
  notificationsCount,
  type Notification
} from '../utilities/notifications';
import TimeAgo from './TimeAgo.vue';

async function enablePushNotifications() {
  if (!(await pushNotifications.subscribePushNotifications())) {
    alert(
      'Notifications are denied, click on the icon before the URL address and enable them manually.\n\nAlso check if option "Use Google services for push messaging" is enabled in your browser privacy settings.'
    );
  }
}

async function openNotification(notification: Notification) {
  if (notification.public) {
    await notifications.markRead(notification.id);
  }

  document.location.href = notification.action_object_url;
}

const getFilteredNotifications = (notifications: Readonly<Notification[]>) => {
  const ret = notifications.slice();
  ret.sort((a, b) => {
    const sortByImportantOrUnread =
      Number((b.important || 0) && b.unread) - Number((a.important || 0) && a.unread);
    const sortByDate = new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();

    return sortByImportantOrUnread || sortByDate;
  });

  return ret;
};
</script>

<template>
  <li v-if="notifications" class="nav-item dropdown">
    <button
      class="btn nav-link dropdown-toggle"
      href="#"
      type="button"
      data-bs-toggle="dropdown"
      data-bs-auto-close="outside"
      aria-expanded="false"
      title="Notifications"
    >
      <span class="iconify" data-icon="bi:bell"></span>
      <span class="d-md-none ms-1">Notifications</span>
      <span
        v-if="notificationsCount > 0"
        :class="`badge ${
          importantNotificationsCount >= 1 ? 'text-bg-danger' : 'text-bg-warning'
        } border border-light rounded-pill`"
      >
        {{ notificationsCount }}
        <span class="visually-hidden">New alerts</span>
      </span>
    </button>

    <div class="dropdown-menu dropdown-menu-end shadow p-0 rounded dropdown-menu-custom">
      <ul class="list-group list-group-flush" style="max-height: 50vh; overflow-y: auto">
        <li class="list-group-item">
          <div class="d-flex align-items-center">
            <div>
              Notifications<template v-if="notificationsCount > 0">
                &nbsp;({{ notificationsCount }})
              </template>
            </div>

            <div class="ms-auto">
              <button
                v-if="pushNotifications.ref.value.supported && !pushNotifications.ref.value.enabled"
                class="btn text-body"
                title="Enable desktop notifications"
                @click="enablePushNotifications"
              >
                <span class="iconify" data-icon="ic:outline-notifications-active"></span>
              </button>
              <button
                class="btn text-body"
                :class="{ 'text-muted': notificationsCount <= 0 }"
                title="Clear all notifications"
                @click="notifications.markAllRead"
              >
                <span class="iconify" data-icon="mdi:notification-clear-all"></span>
              </button>
            </div>
          </div>
        </li>
        <template v-if="notifications.notificationsRef.value.length > 0">
          <li
            v-for="item in getFilteredNotifications(notifications.notificationsRef.value)"
            :key="item.id"
            class="list-group-item p-1 d-flex align-items-center justify-content-between"
            :class="{ 'text-body-secondary': !item.unread || !item.important }"
          >
            <div>
              <strong>{{ item.actor }}&nbsp;</strong>
              <div v-if="item.custom_text" v-html="item.custom_text" />

              <template v-else>
                {{ item.verb }}

                <a
                  v-if="item.action_object_url"
                  :href="item.action_object_url"
                  @click.prevent="openNotification(item)"
                  @auxclick="notifications.markRead(item.id)"
                >
                  {{ item.action_object }}
                </a>
                <template v-else>{item.action_object}</template>

                <template v-if="item.target"> on {{ item.target }}</template>
              </template>
              <span>&nbsp;(<TimeAgo :datetime="item.timestamp" />) </span>
            </div>

            <div>
              <button
                type="button"
                :hidden="!item.unread"
                class="btn-close"
                aria-label="Close"
                @click="notifications.markRead(item.id)"
              ></button>
            </div>
          </li>
        </template>
        <span v-else class="list-group-item p-1 text-center">There are no notifications!</span>
      </ul>
    </div>
  </li>
</template>

<style>
/* 768px - md (medium) bootstrap breakpoint; when the navbar collapses, this gets disabled */
@media (min-width: 768px) {
  .dropdown-menu-custom {
    min-width: 26rem;
  }
}
</style>
