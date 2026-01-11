<script setup>
import { ref } from 'vue';

const props = defineProps({
  content: {
    type: [String, Function],
    required: true
  },
  title: {
    type: String,
    default: 'Copy to clipboard'
  }
});

// TODO: Rework this tooltip to use global modal system instead of local implementation
const tooltip = ref(null);

// This method originally is not working on development environment (Without HTTPS).
// More can be found here: https://stackoverflow.com/a/71876238
const copy = (event) => {
  const resolved = typeof props.content === 'function' ? props.content() : props.content;
  // navigator.clipboard.writeText(resolved ?? '');

  const container = event.currentTarget?.closest('.tooltip-container');

  if (container) {
    tooltip.value = {
      left: container.offsetLeft + container.offsetWidth,
      top: container.offsetTop - 5
    };

    setTimeout(() => {
      tooltip.value = null;
    }, 500);
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
        :style="`left: ${tooltip.left}px; top: ${tooltip.top}px`"
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
</style>
