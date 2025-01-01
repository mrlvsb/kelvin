import { effect, ref } from 'vue';
import { localStorageStore } from './storage';

export type ThemeValue = 'auto' | 'light' | 'dark';
export const currentTheme = localStorageStore<ThemeValue>('theme', 'auto');

//this ref should be used for the current set theme in other parts of application
export const theme = ref<'light' | 'dark'>('light');

//function which detects current theme from media query
const htmlData = document.querySelector('html').dataset;
const themeMedia = window.matchMedia('(prefers-color-scheme: light)');

function detectTheme() {
    theme.value = themeMedia.matches ? 'light' : 'dark';
}

//since we want to have listener on media query to update theme
//every time when user changes theme in browser, we can't use
//computed, and we need to use effect
effect(() => {
    if (currentTheme.value === 'auto') {
        themeMedia.addEventListener('change', detectTheme);
        detectTheme();
        return;
    }
    //in future if this will became SPA, and ColorTheme component will not
    //be presented on every page we should call this in onUnmounted
    themeMedia.removeEventListener('change', detectTheme);

    theme.value = currentTheme.value;
});

//every time theme changes we want to update dataset in
//html tag for bootstrap to change theme
effect(() => {
    htmlData.bsTheme = theme.value;
});
