axios.defaults.headers.common = {
  "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content,
};

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

Vue.component('notifications', {
  props: ['url'],
  data() {
    return {
      unread_count: null,
      notifications: [],
			show: false,
    };
  },
  template: `
  <span style="position: relative">
    <span v-on:click="click" style="cursor: pointer">
      <img src="/static/notify_icon.png" style="height: 15px;" />
      <span class="badge badge-pill badge-danger" style="margin-left: -3px" v-if="unread_count > 0">{{ unread_count }}</span>
    </span>
    <div style="position: absolute; width: 300px; right: 0px; z-index: 2; background: whitesmoke;" v-if="show">
				<ul class="list-group">
					<li class="list-group-item" style="background-color: rgba(0,0,0,.03)">
						Notifications <span v-if="unread_count > 0">({{ unread_count }})</span>
						<span class="float-right" style="cursor: pointer" v-on:click="markAllRead" :key="unread_count">
              <i class="far" v-bind:class="{'fa-circle': unread_count == 0, 'fa-times-circle': unread_count != 0}"></i>
            </span>
					</li>
					<div style="max-height: 300px; overflow-y: auto; font-size: 80%;">
            <template v-if="notifications.length > 0">
              <li v-for="(item, _) in notifications" class='list-group-item p-1' v-bind:class="{'list-group-item-light': !item.unread}">
                <div style="float: right">
                  <button v-bind:class="{'invisible': !item.unread}" class="btn p-0" v-on:click={markRead(item.id)}>&times;</button>
                </div>
                <div>
                  <strong v-if="item.actor_full_name">{{ item.actor_full_name }}</strong>
                  <strong v-else>{{ item.actor }}</strong>
                  {{ item.verb }} 

                  <a v-on:click={markReadRedirect(item.id)} :href="item.action_object_url" v-if="item.action_object_url">{{ item.action_object }}</a>
                  <span v-else>{{ item.action_object }}</span>
                  <span v-if="item.target">on {{ item.target }}</span>
                  (<timeago
                    :datetime="item.timestamp"
                    :title="new Date(item.timestamp).toLocaleString('cs')"></timeago>)
                </div>
              </li>
            </template>
            <span class="list-group-item p-1 text-center" v-else>There are no notifications!</span>
					</div>
				</ul>
    </div>
  </span>`,
  methods: {
    markAllRead() {
      axios.post('/notification/mark_as_read').then(() => {
        this.refresh();
      });
    },
    markRead(id) {
      const item = this.notifications.find((item) => item.id == id);
      if(item) {
        axios.post('/notification/mark_as_read/' + id).then(() => {
          item.unread = false;
        });
      }
    },
    markReadRedirect(id) {
      const item = this.notifications.find((item) => item.id == id);
      if(item) {
        axios.post('/notification/mark_as_read/' + id).then(() => {
            document.location.href = item.action_object_url;
        });
      }
    },
    refresh() {
      axios.get('/notification/all').then((response) => {
        this.unread_count = response.data.unread_count;
        this.notifications = response.data.notifications;
      })
    },
    click() {
      this.show = !this.show; 
    },
  },
  mounted() {
    document.body.addEventListener('click', (evt) => {
      if(!this.$el.contains(evt.target)) {
        this.show = false;
      }
    });
		this.refresh();
//    setInterval(this.refresh, 5000);

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/static/service-worker.js').then((reg) => {
        if (!(reg.showNotification) || Notification.permission === 'denied' || !('PushManager' in window)) {
          return;
        }
        let key = document.querySelector('meta[name="django-webpush-vapid-key"]').content;
        if(!key) {
          return;
        }

				reg.pushManager.getSubscription().then((sub) => {
            if(sub) {
              // already registered, pass false to next then handler
              return false;
            }

            return reg.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: urlB64ToUint8Array(key),
            }).catch(error => {}); // ignore errors if user clicks to disable notifications
				}).then((sub) => {
          if(!sub) {
            // already registered
            return;
          }

					let browser = navigator.userAgent.match(/(firefox|msie|chrome|safari|trident)/ig)[0].toLowerCase();
					let data = {
            status_type: 'subscribe',
						subscription: sub.toJSON(),
						browser: browser,
						group: null,
					};

					fetch('/webpush/save_information', {
            method: 'post',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data),
            credentials: 'include'
					}).then((response) => {
            if(response.status != 201) {
              alert('Subscribe failed');
            }
          });
				});
      });
    }
  },
});

Vue.use(window.VueTimeago, {
  name: 'Timeago',
  locale: 'en'
});

new Vue({
  el: '#notifications',
});
