<script setup lang="ts">
import { ref } from 'vue';
import VueModal from './VueModal.vue';

const showModal = ref(false);

const props = defineProps({
  formId: { type: String, default: '' }
});

function setFlag(proceed: boolean) {
  if (proceed) {
    let form = document.getElementById(props.formId) as HTMLFormElement;
    form.submit();
  }
  showModal.value = false;
}
</script>

<template>
  <input
    type="button"
    value="Mark as final"
    class="btn btn-sm btn-primary"
    @click="showModal = true"
  />
  <VueModal
    :open="showModal"
    title="Send final solution"
    proceed-button-label="Mark solution as final"
    :on-closed="setFlag"
  >
    If you mark the task as final, you won’t be able to submit additional solutions or view the
    existing ones. <br />
    <strong>Are you sure you want to continue?</strong>
  </VueModal>
</template>
