<script setup lang="ts">
import Loader from './Loader.vue';

defineProps<{
  childComponent: object;
}>();
</script>

<template>
  <Suspense>
    <component :is="childComponent" v-bind="$attrs" />
    <template #fallback>
      <div class="d-flex justify-content-center loading-animation">
        <Loader />
      </div>
    </template>
  </Suspense>
</template>
