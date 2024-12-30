<script lang="ts" setup>
/**
 * This component is used to select theme used on website.
 * After opening the dropdown, it shows the list of avalable color themes.
 * Upon chosing the theme, it will update binded value to this component
 * It is available to both teachers and students, and it is accesible from
 * main layout on each page, next to notification bell.
 */

import 'bootstrap/js/dist/dropdown';
import 'bootstrap/js/dist/button';
import { type ThemeValue } from '../utilities/theme';

const theme = defineModel<ThemeValue>('theme');

const THEMES = {
  auto: {
    icon: 'bi-circle-half',
    name: 'Auto'
  },
  light: {
    icon: 'bi-sun',
    name: 'Light mode'
  },
  dark: {
    icon: 'bi-moon-stars',
    name: 'Dark mode'
  }
} as const;
</script>

<template>
  <li class="nav-item dropdown">
    <button
      class="btn nav-link dropdown-toggle"
      href="#"
      type="button"
      data-bs-toggle="dropdown"
      aria-expanded="false"
      title="Change theme"
    >
      <i :class="`bi ${THEMES[theme]?.icon ?? 'bi-circle-half'}`"></i>
      <span class="d-md-none ms-1">Change theme</span>
    </button>
    <ul class="dropdown-menu dropdown-menu-end shadow">
      <li v-for="(data, key) in THEMES" :key="key">
        <button
          class="d-flex dropdown-item"
          :class="{ active: theme == key }"
          @click="() => (theme = key)"
        >
          <i :class="`me-1 bi ${data.icon}`"></i>{{ data.name }}
          <i class="opacity-75 ms-auto bi bi-check2" :hidden="theme != key"></i>
        </button>
      </li>
    </ul>
  </li>
</template>
