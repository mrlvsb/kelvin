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
<li class="nav-item" use:clickOutside on:click_outside={() => show = false}>
  <button class="btn btn-link nav-link" on:click={() => show = !show}>
    <i class="bi bi-bell"></i>
    {#if $notificationsCount > 0}
      <span class="position-absolute top-0 start-100 translate-middle p-2 {$importantNotificationsCount >= 1 ? 'bg-danger' : 'bg-warning'} border border-light rounded-circle">
        {$notificationsCount}
        <span class="visually-hidden">New alerts</span>
      </span>
    {/if}
  </button>
</li>

    {#if show}
    <div style="position: absolute; width: 300px; right: 0px; z-index: 10;">
				<ul class="list-group">
					<li class="list-group-item">
            <div class="d-flex">
              <div>Notifications {#if $notificationsCount > 0}({$notificationsCount}){/if}</div>

            <div class="ms-auto">
              {#if $pushNotifications.supported && !$pushNotifications.enabled}
              <button class="btn p-0" title="Enable desktop notifications" on:click|preventDefault={enablePushNotifications}>
                <span class="iconify" data-icon="ic:outline-notifications-active"></span>
              </button>
              {/if}

              <button class="btn p-0" class:text-muted={$notificationsCount <= 0} on:click|preventDefault={notifications.markAllRead} title="Clear notifications">
                <span class="iconify" data-icon="mdi:notification-clear-all"></span>
              </button>
            </div>
            </div>
					</li>
					<div style="max-height: 300px; overflow-y: auto; font-size: 80% !important;">
            {#if $notifications.length > 0}
              {#each $notifications.slice().sort((a, b) => ((b.important||0) && b.unread) - ((a.important||0) && a.unread) || b.timestamp - a.timestamp) as item (item.id)}
              <li class='list-group-item p-1' class:list-group-item-light={!item.unread || !item.important}>
                <div style="float: right">
                  <button class:invisible={!item.unread} class="btn p-0" on:click|preventDefault={() => notifications.markRead(item.id)}>&times;</button>
                </div>
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
                  <span style="white-space:nowrap">
                    (<TimeAgo datetime={item.timestamp} />)
                  </span>
                </div>
              </li>
              {/each}
            {:else}
            <span class="list-group-item p-1 text-center" v-else>There are no notifications!</span>
            {/if}
					</div>
				</ul>
    </div>
    {/if}
{/if}
