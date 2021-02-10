<script>
import {notifications, pushNotifications} from './notifications.js'
import TimeAgo from './TimeAgo.svelte'
import {clickOutside} from './utils'
import {localStorageStore} from './utils.js'

let show = false;
let showOnlyUnread = localStorageStore('notification/showonlyunread', false);

async function enablePushNotifications() {
  if(!(await pushNotifications.subscribePushNotifications())) {
    alert('Notifications are denied, click on the icon before the URL address and enable them manually.');
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
<span style="position: relative" use:clickOutside on:click_outside={() => show = false}>
    <span on:click={() => show = !show} style="cursor: pointer">
      <img src="/static/notify_icon.png" style="height: 15px;" />
      {#if $notifications.unread_count > 0}
        <span class="badge badge-pill badge-danger" style="margin-left: -3px">{$notifications.unread_count}</span>
      {/if}
    </span>

    {#if show}
    <div style="position: absolute; width: 300px; right: 0px; z-index: 10; background: whitesmoke;">
				<ul class="list-group">
					<li class="list-group-item" style="background-color: rgba(0,0,0,.03)">
            Notifications {#if $notifications.unread_count > 0}({$notifications.unread_count}){/if}

            <div class="float-right">
              {#if $pushNotifications.supported && !$pushNotifications.enabled}
              <button class="btn p-0" title="Enable desktop notifications" on:click|preventDefault={enablePushNotifications}>
                <span class="iconify" data-icon="ic:outline-notifications-active"></span>
              </button>
              {/if}

              <button class="btn p-0" on:click={() => $showOnlyUnread = !$showOnlyUnread}>
                {#if $showOnlyUnread}
                  <span title="Show all notifications."><span class="iconify" data-icon="ic:sharp-mark-email-read" data-inline="false"></span></span>
                {:else}
                  <span title="Show only unread notifications."><span class="iconify" data-icon="ic:sharp-markunread" data-inline="false"></span></span>
                {/if}
              </button>

              <button class="btn p-0" class:text-muted={$notifications.unread_count <= 0} on:click|preventDefault={notifications.markAllRead} title="Clear notifications">
                <span class="iconify" data-icon="mdi:notification-clear-all"></span>
              </button>
            </div>
					</li>
					<div style="max-height: 300px; overflow-y: auto; font-size: 80% !important;">
            {#if $notifications.notifications.length > 0}
              {#each $notifications.notifications.filter(i => !$showOnlyUnread || i.unread) as item}
              <li class='list-group-item p-1' class:list-group-item-light={!item.unread}>
                <div style="float: right">
                  <button class:invisible={!item.unread} class="btn p-0" on:click|preventDefault={() => notifications.markRead(item.id)}>&times;</button>
                </div>
                <div>
                  <strong>{ item.actor }</strong>
                  { item.verb }

                  {#if item.action_object_url}
                    <a href={item.action_object_url} on:click|preventDefault={() => openNotification(item)}>
                      { item.action_object }
                    </a>
                  {:else}
                    { item.action_object }
                  {/if}

                  {#if item.target}on { item.target }{/if}
                  (<TimeAgo datetime={item.timestamp} />)
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
  </span>
{/if}
