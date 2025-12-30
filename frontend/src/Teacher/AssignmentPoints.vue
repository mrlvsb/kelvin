<script setup lang="ts">
import { ref } from 'vue';
import { getFromAPI } from '../utilities/api';

interface Props {
  submits: number;
  link: string;
  color: string;
  assigned_points: string;
  login: string;
  task: string;
  submit_id: number;
}

const props = defineProps<Props>();

const show = ref(false);
const saving = ref(false);
const value = ref(props.assigned_points);

// Event handlers
function hide() {
  show.value = false;
}

function click(e: Event) {
  const target = e.target as HTMLElement;
  const classList = target.classList;
  if (classList.contains('overlay') || classList.contains('inner')) {
    show.value = false;
  }
}

function ctxMenu() {
  if (window.innerWidth < 768) {
    show.value = true;
  }
}

async function save() {
  saving.value = true;

  const form = new FormData();
  form.append('assigned_points', value.value);

  await getFromAPI(`/submit/${props.submit_id}/points`, 'POST', form);

  // FIXME: Update prop (normally you’d emit this change instead of modifying props directly)
  // props.assigned_points = value.value; ❌ not allowed
  // You might need to emit the change if parent cares

  saving.value = false;
  show.value = false;
}
</script>

<template>
  <div ref="container" @contextmenu.prevent="ctxMenu" @keydown.esc="hide" @click="click">
    <a v-if="submits !== 0" :href="link" :style="{ color: color }">
      {{ isNaN(parseFloat(assigned_points)) ? '?' : assigned_points }}
    </a>

    <div v-if="show" class="overlay">
      <div class="inner">
        <h2>{{ login }}</h2>
        <h3>{{ task }}</h3>
        <form @submit.prevent="save">
          <input v-model.number="value" class="form-control" type="number" autofocus />
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
