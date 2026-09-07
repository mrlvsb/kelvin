<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import SyncLoader from './SyncLoader.vue';
import { getFromAPI } from '../utilities/api';

const props = defineProps<{
  submitid: string | number;
}>();

// null until the first poll resolves, so we don't flash the "being processed"
// panel before knowing the real state (the job may already be finished, in
// which case update() reloads the page).
const jobStatus = ref<string | null>(null);
const message = ref('');
let timer: ReturnType<typeof setTimeout> | undefined;

async function update() {
  const json = await getFromAPI<{ finished: boolean; status: string; message: string }>(
    `/submit/${props.submitid}/pipeline`
  );

  if (!json) {
    // Transient failure - keep polling.
    timer = setTimeout(update, 1000);
    return;
  }

  if (json.finished) {
    document.location.reload();
    return;
  }

  jobStatus.value = json.status;
  message.value = json.message;

  // A failed evaluation is terminal - show the message and stop polling.
  if (json.status !== 'failed') {
    timer = setTimeout(update, 1000);
  }
}

onMounted(update);
onUnmounted(() => clearTimeout(timer));
</script>

<template>
  <template v-if="jobStatus === 'failed'">
    <h2 class="text-danger text-center">
      <b>Evaluation failed - please contact your teacher.</b>
    </h2>
    <pre>{{ message }}</pre>
  </template>
  <div v-else class="main">
    <template v-if="jobStatus !== null">
      Your submit is being processed, please wait.<br />
      Your submit has been uploaded to Kelvin, it won't be lost if you close the browser.<br />
      {{ jobStatus }}
    </template>
    <div class="d-flex justify-content-center">
      <SyncLoader />
    </div>
  </div>
</template>

<style scoped>
div.main {
  font-size: 1.5rem;
  font-weight: bold;
  text-align: center;
}
</style>
