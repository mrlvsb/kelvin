<script setup lang="ts">
defineProps({
  open: { type: Boolean, default: false, required: true },
  title: { type: String, default: '' },
  cancelButtonLabel: { type: String, default: 'Cancel' },
  proceedButtonLabel: { type: String, default: 'Proceed' },
  onClosed: { type: Function, default: null, required: true }
});
</script>

<template>
  <div
    v-if="open"
    class="modal"
    id="kelvin-modal"
    tabindex="-1"
    role="dialog"
    aria-labelledby="Modal"
    aria-hidden="false"
  >
    <div class="modal-dialog" role="document">
      <div class="modal-content">
        <div class="modal-header">
          <h5 id="sampleModalLabel" class="modal-title">{{ title }}</h5>
          <button
            type="button"
            class="btn-close"
            aria-label="Close"
            @click="onClosed(false)"
          ></button>
        </div>

        <div class="modal-body">
          <slot></slot>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="onClosed(false)">
            {{ cancelButtonLabel }}
          </button>

          <button type="button" class="btn btn-primary" @click="onClosed(true)">
            {{ proceedButtonLabel }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal {
  display: block;
}
</style>
