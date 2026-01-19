<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import type { ToastStatus, ToastOptions } from '../types/Toast';

type ToastItem = ToastOptions & { id: number };

const toasts = ref<ToastItem[]>([]);
let toastId = 0;

const statusClasses: Record<ToastStatus, string> = {
  success: 'text-bg-success',
  warning: 'text-bg-warning',
  error: 'text-bg-danger'
};

const addToast = (toastOptions: ToastOptions) => {
  const id = toastId++;
  const duration = toastOptions.duration ?? 4000;

  toasts.value = [
    ...toasts.value,
    {
      id,
      title: toastOptions.title,
      header: toastOptions.header,
      body: toastOptions.body,
      type: toastOptions.type ?? 'success',
      duration
    }
  ];

  if (duration > 0) {
    window.setTimeout(() => {
      toasts.value = toasts.value.filter((toastItem) => toastItem.id !== id);
    }, duration);
  }
};

const normalizeWindowToastOptions = (windowToastOptions: ToastOptions): ToastOptions => {
  return {
    title: windowToastOptions.title,
    body: windowToastOptions.message,
    type: windowToastOptions.type ?? 'success',
    duration: windowToastOptions.duration
  };
};

onMounted(() => {
  window.showToast = (windowToastOptions: ToastOptions) => {
    const toastOptions: ToastOptions = normalizeWindowToastOptions(windowToastOptions);
    addToast(toastOptions);
  };

  window.toastApi = {
    success: (message: string, options?: Omit<ToastOptions, 'message' | 'type'>) => {
      addToast({
        body: message,
        type: 'success',
        title: options?.title,
        duration: options?.duration
      });
    },

    warning: (message: string, options?: Omit<ToastOptions, 'message' | 'type'>) => {
      addToast({
        body: message,
        type: 'warning',
        title: options?.title,
        duration: options?.duration
      });
    },

    error: (message: string, options?: Omit<ToastOptions, 'message' | 'type'>) => {
      addToast({
        body: message,
        type: 'error',
        title: options?.title,
        duration: options?.duration
      });
    }
  };
});

onBeforeUnmount(() => {
  delete window.showToast;
  delete window.toastApi;
});
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
        <div v-if="toastItem.title || toastItem.header" class="toast-header">
          <strong class="me-auto">{{ toastItem.header || toastItem.title }}</strong>
          <button
            type="button"
            class="btn-close"
            aria-label="Close"
            @click="toasts = toasts.filter((toast) => toast.id !== toastItem.id)"
          />
        </div>

        <div class="d-flex">
          <div class="toast-body">{{ toastItem.body }}</div>

          <button
            v-if="!toastItem.title && !toastItem.header"
            type="button"
            class="btn-close me-2 m-auto"
            aria-label="Close"
            @click="toasts = toasts.filter((toast) => toast.id !== toastItem.id)"
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
