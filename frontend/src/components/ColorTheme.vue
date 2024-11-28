<script lang="ts" setup>
/**
 * This component displays an icon with current color theme of website.
 * After opening the dropdown, it shows the list of avalable color themes.
 * Upon chosing the theme, it will change theme of website and save it to localStorage.
 * It is available to both teachers and students, and it is accesible from
 * main layout on each page, next to notification bell.
 */

import 'bootstrap/js/dist/dropdown';
import 'bootstrap/js/dist/button';
import { currentTheme, type ThemeValue } from '../utilities/storage';
import { localStorageStore } from '../utilities/storage';
import { watch } from 'vue';

const curTheme = localStorageStore<ThemeValue>('color-theme', 'auto');

const htmlData = document.querySelector('html').dataset;

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

function detectTheme() {
  const colorScheme = window.matchMedia('(prefers-color-scheme: light)');
  const theme = colorScheme.matches ? 'light' : 'dark';
  htmlData.bsTheme = theme;
  currentTheme.value = theme;
}

function selectTheme(theme: ThemeValue) {
  if (theme == 'auto') {
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', detectTheme);
  }
  // theme is manually selected
  window.matchMedia('(prefers-color-scheme: light)').removeEventListener('change', detectTheme);

  curTheme.value = theme;
  htmlData.bsTheme = theme;
}

//sync currentTheme with value in localStorage
watch(
  curTheme,
  (value) => {
    if (value !== 'auto') {
      currentTheme.value = curTheme.value;
      return;
    }

    detectTheme();
  },
  {
    immediate: true
  }
);

if (curTheme.value != 'auto') {
  selectTheme(curTheme.value);
}
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
      <i :class="`bi ${THEMES[curTheme]?.icon ?? 'bi-circle-half'}`"></i>
      <span class="d-md-none ms-1">Change theme</span>
    </button>
    <ul class="dropdown-menu dropdown-menu-end shadow">
      <li v-for="(data, key) in THEMES" :key="key">
        <button
          class="d-flex dropdown-item"
          :class="{ active: curTheme == key }"
          @click="() => selectTheme(key)"
        >
          <i :class="`me-1 bi ${data.icon}`"></i>{{ data.name }}
          <i class="opacity-75 ms-auto bi bi-check2" :hidden="curTheme != key"></i>
        </button>
      </li>
    </ul>
  </li>
</template>
