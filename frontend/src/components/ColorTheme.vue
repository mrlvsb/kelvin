<script lang="ts" setup>
import { currentTheme } from '../utilities/theme';
import ThemeSelector from './ThemeSelector.vue';
</script>

<template>
  <ThemeSelector v-model:theme="currentTheme" />
</template>
