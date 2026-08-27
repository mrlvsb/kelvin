import { writable } from 'svelte/store';

// Populated by App.svelte, the root of the Svelte home page. Every Vue page that
// needs the current user/semester fetches /api/info itself (utilities/global.ts)
// at its root and passes the result down as props, so /api/info is not loaded
// unconditionally on every page.
export const semester = writable();
export const user = writable();
