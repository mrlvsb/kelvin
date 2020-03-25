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
						<span class="btn" class="float-right" style="cursor: pointer" v-on:click="markAllRead">&times;</span>
					</li>
					<div style="max-height: 300px; overflow-y: auto; font-size: 80%;">
            <template v-if="notifications.length > 0">
              <li v-for="(item, _) in notifications" class='list-group-item p-1' v-bind:class="{'list-group-item-light': !item.unread}">
                <strong v-if="item.actor_full_name">{{ item.actor_full_name }}</strong>
                <strong v-else>{{ item.actor }}</strong>
                {{ item.verb }} 

                <a :href="item.action_object_url" v-if="item.action_object_url">{{ item.action_object }}</a>
                <span v-else>{{ item.action_object }}</span>
                on 
                {{ item.target }}
              </li>
            </template>
            <li class="list-group-item p-1 text-center" v-else>There are no notifications!</span>
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
		this.refresh();
//    setInterval(this.refresh, 5000);
  },
});

new Vue({
  el: '#notifications',
});
