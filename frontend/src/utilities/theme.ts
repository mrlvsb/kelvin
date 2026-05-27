import { effect, ref } from 'vue';
import { localStorageStore } from './storage';

export type ThemeValue = 'auto' | 'light' | 'dark';
export const currentTheme = localStorageStore<ThemeValue>('theme', 'auto');

//this ref reflects the theme actually applied to <html data-bs-theme>. It is
//kept in sync with that attribute regardless of which switcher set it: the Vue
//ThemeSelector (via currentTheme below) or the legacy Svelte ColorTheme, which
//writes data-bs-theme directly without going through currentTheme.
export const theme = ref<'light' | 'dark'>('light');

const html = document.querySelector('html');
const htmlData = html.dataset;
const themeMedia = window.matchMedia('(prefers-color-scheme: light)');

//Vue ThemeSelector path: apply the stored preference to the html attribute.
function applyCurrentTheme() {
    if (currentTheme.value === 'auto') {
        htmlData.bsTheme = themeMedia.matches ? 'light' : 'dark';
    } else {
        htmlData.bsTheme = currentTheme.value;
    }
}

//since we want to have listener on media query to update theme
//every time when user changes theme in browser, we can't use
//computed, and we need to use effect
effect(() => {
    if (currentTheme.value === 'auto') {
        themeMedia.addEventListener('change', applyCurrentTheme);
    } else {
        //in future if this will became SPA, and ColorTheme component will not
        //be presented on every page we should call this in onUnmounted
        themeMedia.removeEventListener('change', applyCurrentTheme);
    }
    applyCurrentTheme();
});

//mirror the applied data-bs-theme attribute into the reactive theme value, so
//components react no matter which switcher changed it.
function syncThemeFromDom() {
    theme.value = htmlData.bsTheme === 'dark' ? 'dark' : 'light';
}
syncThemeFromDom();

new MutationObserver(syncThemeFromDom).observe(html, {
    attributes: true,
    attributeFilter: ['data-bs-theme']
});
