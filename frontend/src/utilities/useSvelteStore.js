import { onUnmounted, ref } from 'vue';

export const useSvelteStore = (store, initialValue = undefined) => {
    const value = ref(initialValue);
    const unsubscribe = store.subscribe((nextValue) => {
        value.value = nextValue;
    });

    onUnmounted(() => {
        if (unsubscribe) {
            unsubscribe();
        }
    });

    return value;
};
