import { ref, watch, type Ref } from 'vue';

const localStorageStores: Record<string, Ref<unknown>> = {};

/**
 * Returns ref to value in localStorage. When updated, automatically saved to localStorage.
 *
 * @param key Key of localStorage item
 * @param initialValue Initial value of item
 *
 * @returns {@link Ref} to localStorage value
 */
export const localStorageStore = <$Type>(key: string, initialValue: $Type): Ref<$Type> => {
    if (!(key in localStorageStores)) {
        const saved = localStorage.getItem(key);
        if (saved) {
            try {
                initialValue = JSON.parse(saved);
            } catch (exception) {
                console.log(`Failed to load ${key}: ${exception}`);
            }
        }

        const value = ref(initialValue);

        localStorageStores[key] = value;
        watch(value, (newValue) => localStorage.setItem(key, JSON.stringify(newValue)));
    }
    return localStorageStores[key] as Ref<$Type>;
};
