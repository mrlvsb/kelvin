<script lang="ts">
//import { fetch as apiFetch } from './api.js';
import { getFromAPI } from '../utilities/api';

export default {
  name: 'AssignmentPoints',
  props: {
    submits: Number,
    link: String,
    color: String,
    assigned_points: Number,
    login: String,
    task: String,
    submit_id: Number
  },
  data() {
    return {
      show: false,
      saving: false,
      value: this.assigned_points
    };
  },
  methods: {
    hide() {
      this.show = false;
    },
    click(e) {
      const classList = e.target.classList;
      if (classList.contains('overlay') || classList.contains('inner')) {
        this.show = false;
      }
    },
    ctxMenu(e) {
      if (window.innerWidth < 768) {
        this.show = true;
      }
    },
    async save() {
      this.saving = true;
      const form = new FormData();
      form.append('assigned_points', this.value);

      await getFromAPI(`/submit/${this.submit_id}/points`, 'POST', form);
      //await apiFetch(`/submit/${this.submit_id}/points`, {
      //  method: 'POST',
      //  body: form,
      //});

      this.assigned_points = this.value;
      this.saving = false;
      this.show = false;
    }
  }
};
</script>

<template>
  <div @contextmenu.prevent="ctxMenu" @keydown.esc="hide" @click="click" ref="container">
    <a v-if="submits !== 0" :href="link" :style="{ color: color }">
      {{ isNaN(parseFloat(assigned_points)) ? '?' : assigned_points }}
    </a>

    <div v-if="show" class="overlay">
      <div class="inner">
        <h2>{{ login }}</h2>
        <h3>{{ task }}</h3>
        <form @submit.prevent="save">
          <input class="form-control" type="number" v-model.number="value" autofocus />
          <button class="btn btn-success mt-1" :disabled="saving">
            <div v-if="saving" class="spinner-border spinner-border-sm" role="status"></div>
            Save
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  top: 0;
  left: 0;
  background: rgba(var(--bs-body-bg-rgb), 0.9);
  width: 100vw;
  height: 100vh;
  z-index: 11;
}

.inner {
  width: 50%;
  display: flex;
  align-items: center;
  height: 100%;
  flex-direction: column;
  flex-wrap: wrap;
  align-content: center;
  margin: 0 auto;
  justify-content: center;
}

button {
  width: 100%;
}
</style>
