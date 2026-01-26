<script lang="ts" setup>
import { onMounted, onUnmounted, ref } from 'vue';

let { src, alt } = defineProps<{
  src: string;
  alt?: string;
}>();

const fullscreenImageSrc = ref<string | null>(null);

const openFullscreenImage = () => {
  fullscreenImageSrc.value = src;
};

const closeFullscreenImage = () => {
  fullscreenImageSrc.value = null;
};

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    closeFullscreenImage();
  }
};

// This function marks the drag event as an internal drag within Kelvin
// to prevent unwanted uploads when dragging images.
const markInternalDrag = (event: DragEvent) => {
  event.dataTransfer?.setData('text/kelvin-internal-drag', 'true');
};

onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <div>
    <img
      :src="src"
      :alt="alt"
      class="preview-image"
      @click="openFullscreenImage"
      @dragstart="markInternalDrag"
    />

    <div
      v-if="fullscreenImageSrc"
      class="fullscreen-overlay"
      role="button"
      aria-label="Close fullscreen image"
      @click="closeFullscreenImage"
    >
      <img
        :src="fullscreenImageSrc"
        class="fullscreen-image"
        :alt="alt"
        @dragstart="markInternalDrag"
      />
    </div>
  </div>
</template>

<style scoped>
.preview-image {
  cursor: zoom-in;
  max-width: 100%;
}

.fullscreen-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  cursor: zoom-out;
}

.fullscreen-image {
  max-width: 95vw;
  max-height: 95vh;
  object-fit: contain;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
}
</style>
