import { ref, onUnmounted, Ref, watch } from 'vue';
import { Readable, Unsubscriber, Writable } from 'svelte/store';

/**
 * Wrap readable Svelte store so it becomes reactive in Vue.
 * Readable means one way data flow Svelte -> Vue, changing ref value has no effect
 *
 * @param store - Svelte store
 * @returns Vue Ref that updates whenever the Svelte store updates
 */
export function useReadableSvelteStore<T>(store: Readable<T>): Ref<T> {
    const value = ref<T>();

    const unsubscribe: Unsubscriber = store.subscribe((v: T) => {
        value.value = v;
    });

    onUnmounted(unsubscribe);

    return value;
}

/**
 * Wrap Writeable Svelte store so it becomes reactive in Vue.
 * This creates both way data binding
 *
 * @param store - Svelte store
 * @returns Vue Ref that updates whenever the Svelte store updates, changing its value change store state
 */
export function useWritableSvelteStore<T>(store: Writable<T>): Ref<T> {
    const value = ref<T>();

    const unsubscribe: Unsubscriber = store.subscribe((v: T) => {
        value.value = v;
    });

    watch(value, (v) => store.set(v));

    onUnmounted(unsubscribe);

    return value;
}
