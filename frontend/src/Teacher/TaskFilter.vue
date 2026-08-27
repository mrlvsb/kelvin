<script setup lang="ts">
import { task_types } from '../taskTypes';
import { theme } from '../utilities/theme';

const taskType = defineModel<string | null>('taskType', { default: null });
</script>

<template>
  <div class="ms-auto">
    <div class="input-group">
      <button
        v-for="{ key, value } in task_types"
        :key="value"
        type="button"
        class="btn"
        :class="[`btn-${theme}`, { active: key === taskType }]"
        @click="taskType = key"
      >
        {{ value }}
      </button>
    </div>
  </div>
</template>
