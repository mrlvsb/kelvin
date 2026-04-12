<script lang="ts" setup>
import { ref } from 'vue';

const props = withDefaults(
  defineProps<{
    content: string | (() => string);
    title?: string;
  }>(),
  {
    title: 'Copy to clipboard'
  }
);

const tooltip = ref(null);

const copy = (event: MouseEvent) => {
  const resolved = typeof props.content === 'function' ? props.content() : props.content;

  try {
    // This method originally is not working on development environment (Without HTTPS).
    // More can be found here: https://stackoverflow.com/a/71876238
    navigator.clipboard.writeText(resolved ?? '');
  } catch (e) {
    console.error('Failed to copy to clipboard', e);
  }

  const container = (event.currentTarget as HTMLElement | null)?.closest(
    '.tooltip-container'
  ) as HTMLElement | null;

  if (container instanceof HTMLElement) {
    tooltip.value = {
      left: container.offsetLeft + container.offsetWidth,
      top: container.offsetTop - 5
    };

    setTimeout(() => {
      tooltip.value = null;
    }, 1000);
  }
};
</script>

<template>
  <span style="position: relative">
    <span class="tooltip-container" :title="title" @click="copy">
      <slot></slot>
    </span>

    <transition name="fade">
      <div
        v-if="tooltip"
        class="tooltip bs-tooltip-right show d-flex align-items-center"
        role="tooltip"
        :style="{ position: 'absolute', left: tooltip.left + 'px', top: tooltip.top + 'px' }"
      >
        <div class="popover-arrow"></div>
        <div class="tooltip-inner">Copied!</div>
      </div>
    </transition>
  </span>
</template>

<style scoped>
span {
  cursor: pointer;
}

.tooltip-inner {
  margin-top: 0.75rem;
}

.fade-enter-active {
  transition: opacity 0.5s ease;
}

.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-enter-to,
.fade-leave-from {
  opacity: 1;
}
</style>
