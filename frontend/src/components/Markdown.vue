<script setup lang="ts">
import { computed, defineProps } from 'vue';
import { safeMarkdown } from '../markdown.js';

const props = defineProps({ content: { type: String, default: '' } });

const renderedContent = computed(() => safeMarkdown(props.content, { breaks: false }));
</script>

<template>
  <div class="md" v-html="renderedContent"></div>
</template>

<style scoped>
.md :deep(h1) {
  font-size: 1.5rem;
}
.md :deep(h2) {
  font-size: 1.4rem;
}
.md :deep(h3) {
  font-size: 1.3rem;
}
.md :deep(h4) {
  font-size: 1.2rem;
}
.md :deep(h5) {
  font-size: 1.1rem;
}
.md :deep(h6) {
  font-size: 1rem;
}
</style>
