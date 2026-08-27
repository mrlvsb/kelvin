<script setup lang="ts">
import { computed, ref } from 'vue';
import { sendFormWithCSRF } from '../utilities/api';

interface Props {
  submits: number;
  link: string;
  color: string;
  assigned_points?: number | null;
  login: string;
  task: string;
  submit_id: number;
  has_final_submit?: boolean;
}

const props = defineProps<Props>();

const show = ref(false);
const saving = ref(false);
const value = ref<number | string>(props.assigned_points ?? '');
// Locally reflects the assigned points after a successful save, mirroring the
// Svelte component which mutated its own prop copy.
const displayPoints = ref<number | string | null | undefined>(props.assigned_points);

// Text shown in the cell: the points if numeric, otherwise "F" for a final
// submit without points, or "?" for an ungraded submit.
const pointsText = computed(() => {
  const p = displayPoints.value;
  if (p === null || p === undefined || p === '' || isNaN(Number(p))) {
    return props.has_final_submit ? 'F' : '?';
  }
  return String(p);
});

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
  form.append('assigned_points', String(value.value));

  await sendFormWithCSRF(`/submit/${props.submit_id}/points`, form);

  displayPoints.value = value.value;
  saving.value = false;
  show.value = false;
}
</script>

<template>
  <div ref="container" @contextmenu.prevent="ctxMenu" @keydown.esc="hide" @click="click">
    <a
      v-if="submits !== 0"
      :href="link"
      :style="{ color: color }"
      :title="pointsText === 'F' ? 'Final' : undefined"
    >
      {{ pointsText }}
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
