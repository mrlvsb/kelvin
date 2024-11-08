import { ref, watch, type Ref } from 'vue';

import { csrfToken } from '../api';

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/**
 * Get data from API
 *
 * @param url url to fetch
 * @param data data which will be sent to the API
 * @param method HTTP method, if you want to override the default GET/POST
 * @note If data is passed, the request will be a POST request, otherwise a GET request, if not overridden by method parameter
 * @param headers Headers for the request
 *
 * @returns $ReturnType, if the request was successful, otherwise undefined
 */
export const getFromAPI = async <$ReturnType>(
    url: string,
    method?: Method,
    data?: unknown,
    headers?: HeadersInit
): Promise<$ReturnType | undefined> => {
    try {
        const response = await fetch(url, {
            method: method || (data ? 'POST' : 'GET'),
            headers,
            body: data ? JSON.stringify(data) : undefined
        });

        if (!response.ok) {
            return undefined;
        }

        const json = await response.json();
        return json as $ReturnType;
    } catch (error) {
        console.error(error);
        return undefined;
    }
};

/**
 * Get data from endpoint with {@link getFromAPI()}, but with already filled header `X-CSRFToken`.
 *
 * @param url url to fetch
 * @param data data which will be sent to the API
 * @param method HTTP method, if you want to override the default GET/POST
 * @note If data is passed, the request will be a POST request, otherwise a GET request, if not overridden by method parameter
 * @param headers Headers for the request
 *
 * @returns $ReturnType, if the request was successful, otherwise undefined
 */
export const getDataWithCSRF = async <$ReturnType>(
    url: string,
    method?: Method,
    data?: unknown,
    headers?: HeadersInit
): Promise<$ReturnType | undefined> => {
    const CSRF = {
        'X-CSRFToken': csrfToken()
    };
    return getFromAPI(url, method, data, headers ? { ...headers, ...CSRF } : CSRF);
};

/**
 * Generate array with range of numbers from start
 *
 * @param size size of the array
 * @param start starting number
 *
 * @returns array of numbers from start to start + size
 */
export const generateRange = (size: number, start = 0) => {
    return Array.from({ length: size }).map((_, i) => i + start);
};

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
