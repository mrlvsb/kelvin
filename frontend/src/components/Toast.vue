<script lang="ts" setup>
import { useToastStore } from '../utilities/toast';

const toastStore = useToastStore();
const toasts = toastStore.toasts;
const statusClasses = toastStore.statusClasses;

function closeToast(toastId: number): void {
  toastStore.removeToast(toastId);
}
</script>

<template>
  <div class="toast-container position-fixed top-0 end-0 p-3">
    <TransitionGroup name="toast" tag="div" class="toast-stack">
      <div
        v-for="toastItem in toasts"
        :key="toastItem.id"
        class="toast show align-items-center border-0"
        :class="statusClasses[toastItem.type ?? 'success']"
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
      >
        <div v-if="toastItem.title" class="toast-header">
          <strong class="me-auto">{{ toastItem.title }}</strong>
          <button
            type="button"
            class="btn-close"
            aria-label="Close"
            @click="closeToast(toastItem.id)"
          />
        </div>

        <div class="d-flex">
          <div class="toast-body">{{ toastItem.message }}</div>

          <button
            v-if="!toastItem.title"
            type="button"
            class="btn-close me-2 m-auto"
            aria-label="Close"
            @click="closeToast(toastItem.id)"
          />
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-stack {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.toast-enter-active {
  transition:
    transform 220ms ease,
    opacity 220ms ease,
    max-height 220ms ease,
    margin 220ms ease,
    padding 220ms ease;
}

.toast-leave-active {
  transition:
    transform 180ms ease,
    opacity 180ms ease,
    max-height 180ms ease,
    margin 180ms ease,
    padding 180ms ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(16px);
  max-height: 0;
  margin-top: 0;
  margin-bottom: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.toast-enter-to,
.toast-leave-from {
  opacity: 1;
  transform: translateX(0);
  max-height: 200px;
}

.toast-move {
  transition: transform 220ms ease;
}
</style>
