import { onUnmounted, ref, type Ref } from 'vue';

export type SvelteStore<T> = {
    subscribe: (run: (value: T) => void) => () => void;
};

export const useSvelteStore = <T>(store: SvelteStore<T>, initialValue?: T): Ref<T | undefined> => {
    const value = ref<T | undefined>(initialValue) as Ref<T | undefined>;
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
