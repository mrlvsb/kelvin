<script>
import {notifications, pushNotifications, importantNotificationsCount, notificationsCount} from './notifications.js'
import TimeAgo from './TimeAgo.svelte'
import {clickOutside} from './utils'
import {localStorageStore} from './utils.js'

let show = false;
let showOnlyUnread = localStorageStore('notification/showonlyunread', false);

async function enablePushNotifications() {
  if(!(await pushNotifications.subscribePushNotifications())) {
    alert('Notifications are denied, click on the icon before the URL address and enable them manually.\n\nAlso check if option "Use Google services for push messaging" is enabled in your browser privacy settings.');
  }
}

async function openNotification(notification) {
  if(notification.public) {
    await notifications.markRead(notification.id);
  }

  document.location.href = notification.action_object_url;
}

</script>

{#if $notifications}
<li class="nav-item dropdown">
  <button class="btn btn-link nav-link dropdown-toggle" href="#" type="button" data-bs-toggle="dropdown" data-bs-auto-close="outside" aria-expanded="false" title="Notifications">
    <i class="bi bi-bell"></i>
    <span class="d-md-none ms-1">Notifications</span>
    {#if $notificationsCount > 0}
      <span class="badge {$importantNotificationsCount >= 1 ? 'text-bg-danger' : 'text-bg-warning'} border border-light rounded-pill">
        {$notificationsCount}
        <span class="visually-hidden">New alerts</span>
      </span>
    {/if}
    </button>

    <div class="dropdown-menu dropdown-menu-end shadow p-0 rounded dropdown-menu-custom">
      <ul class="list-group list-group-flush">
        <li class="list-group-item">
          <div class="d-flex align-items-center">
            <div>Notifications{#if $notificationsCount > 0}&nbsp;({$notificationsCount}){/if}</div>

            <div class="ms-auto">
              {#if !$pushNotifications.supported && !$pushNotifications.enabled}
              <button class="btn text-body" title="Enable desktop notifications" on:click={enablePushNotifications}>
                <span class="iconify" data-icon="ic:outline-notifications-active"></span>
              </button>
              {/if}
              <button class="btn text-body" class:text-muted={$notificationsCount <= 0} on:click={notifications.markAllRead} title="Clear all notifications">
                <span class="iconify" data-icon="mdi:notification-clear-all"></span>
              </button>
            </div>
        </li>
        {#if $notifications.length > 0}
              {#each $notifications.slice().sort((a, b) => ((b.important||0) && b.unread) - ((a.important||0) && a.unread) || b.timestamp - a.timestamp) as item (item.id)}
              <li class='list-group-item p-1 d-flex align-items-center justify-content-between' class:text-body-secondary={!item.unread || !item.important}>
                <div>
                  <strong>{ item.actor }</strong>
                  {#if item.custom_text}
                    {@html item.custom_text}
                  {:else}
                    { item.verb }

                    {#if item.action_object_url}
                      <a href={item.action_object_url} on:click|preventDefault={() => openNotification(item)} on:auxclick={() => notifications.markRead(item.id)}>
                        { item.action_object }
                      </a>
                    {:else}
                      { item.action_object }
                    {/if}

                    {#if item.target}on { item.target }{/if}
                  {/if}
                  <span>
                    (<TimeAgo datetime={item.timestamp} />)
                  </span>
                </div>
                <div>
                  <button type="button" hidden={!item.unread} class="btn-close" aria-label="Close" on:click={() => notifications.markRead(item.id)}></button>
                </div>
              </li>
              {/each}
            {:else}
            <span class="list-group-item p-1 text-center" v-else>There are no notifications!</span>
            {/if}
      </ul>
    </div>
</li>
{/if}

<style>
  /* 768px - md (medium) bootstrap breakpoint; when the navbar collapses, this gets disabled */
  @media(min-width: 768px) {
    .dropdown-menu-custom {
      min-width: 26rem;
    }
  }
</style>
