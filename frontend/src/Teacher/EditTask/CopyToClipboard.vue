<script setup lang="ts">
/**
 * Displays a button with given text and title; once clicked it copies content to clipboard
 * and show a small animation informing user about the action
 */
import { ref } from 'vue';

/**
 * @prop {string} content - content to copy to clipboard
 * @prop {string} title   - appears when the user moves the mouse over the button
 */
let { content, title = 'Copy to clipboard' } = defineProps<{
  content?: string;
  title: string;
}>();

/**
 * Pop up message coordinates
 */
interface PopUp {
  left: number;
  top: number;
}

const tooltip = ref<PopUp | null>(null);

function copy(e: MouseEvent): void {
  navigator.clipboard.writeText(content);

  let spanElement: HTMLElement = e.target as HTMLElement;
  let container: HTMLElement = spanElement.closest('.tooltip-container') as HTMLElement;
  tooltip.value = {
    left: container.offsetLeft + container.offsetWidth,
    top: container.offsetTop - 5
  };

  setTimeout(() => (tooltip.value = null), 1500);
}
</script>

<template>
  <span style="position: relative">
    <span class="tooltip-container" :title="title" @click="copy">
      <slot></slot>
    </span>
    <Transition name="fade">
      <div
        v-if="tooltip"
        class="tooltip bs-tooltip-right show d-flex align-items-center"
        role="tooltip"
        :style="{ left: tooltip.left + 'px', top: tooltip.top + 'px' }"
      >
        <div class="popover-arrow"></div>
        <div class="tooltip-inner">Copied!</div>
      </div>
    </Transition>
  </span>
</template>

<style scoped>
span {
  cursor: pointer;
}

.fade-enter-active {
  transition: opacity 2s ease;
}

.fade-leave-active {
  transition: opacity 0.1s ease;
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
