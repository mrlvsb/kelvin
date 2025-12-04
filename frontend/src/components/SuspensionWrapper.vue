<script setup lang="ts">
import SyncLoader from '../Teacher/EditTask/SyncLoader.vue';

defineProps<{
  childComponent: object;
}>();
</script>

<template>
  <Suspense>
    <component :is="childComponent" v-bind="$attrs" />
    <template #fallback>
      <div class="d-flex justify-content-center loading-animation">
        <SyncLoader />
      </div>
    </template>
  </Suspense>
</template>
