import { computed, ref } from 'vue';
import type { ComputedRef, Ref } from 'vue';
import type { ToastApi, ToastOptions, ToastStatus } from '../types/Toast';

export type ToastItem = ToastOptions & { id: number };

const toasts: Ref<ToastItem[]> = ref<ToastItem[]>([]);
let nextToastId: number = 0;

const statusClasses: Record<ToastStatus, string> = {
    success: 'text-bg-success',
    warning: 'text-bg-warning',
    error: 'text-bg-danger'
};

function normalizeToastOptions(toastOptions: ToastOptions): ToastOptions {
    return {
        title: toastOptions.title,
        message: toastOptions.message,
        type: toastOptions.type ?? 'success',
        duration: toastOptions.duration ?? 4000
    };
}

function removeToast(toastId: number): void {
    toasts.value = toasts.value.filter((toastItem: ToastItem) => toastItem.id !== toastId);
}

function addToast(toastOptions: ToastOptions): void {
    const normalizedOptions: ToastOptions = normalizeToastOptions(toastOptions);
    const toastId: number = nextToastId++;

    const toastItem: ToastItem = {
        id: toastId,
        title: normalizedOptions.title,
        message: normalizedOptions.message,
        type: normalizedOptions.type,
        duration: normalizedOptions.duration
    };

    toasts.value = [...toasts.value, toastItem];

    const duration: number = toastItem.duration ?? 0;
    if (duration > 0) {
        window.setTimeout(() => removeToast(toastId), duration);
    }
}

type ToastStore = {
    toasts: ComputedRef<readonly ToastItem[]>;
    statusClasses: Record<ToastStatus, string>;
    addToast: (toastOptions: ToastOptions) => void;
    removeToast: (toastId: number) => void;
};

const readonlyToasts: ComputedRef<readonly ToastItem[]> = computed(() => toasts.value);

export function useToastStore(): ToastStore {
    return {
        toasts: readonlyToasts,
        statusClasses,
        addToast,
        removeToast
    };
}

export function showToast(toastOptions: ToastOptions): void {
    addToast(toastOptions);
}

type ToastMethodOptions = Omit<ToastOptions, 'message' | 'type'>;

export const toastApi: ToastApi = {
    success: (message: string, options?: ToastMethodOptions) => {
        addToast({
            message,
            type: 'success',
            title: options?.title,
            duration: options?.duration
        });
    },

    warning: (message: string, options?: ToastMethodOptions) => {
        addToast({
            message,
            type: 'warning',
            title: options?.title,
            duration: options?.duration
        });
    },

    error: (message: string, options?: ToastMethodOptions) => {
        addToast({
            message,
            type: 'error',
            title: options?.title,
            duration: options?.duration
        });
    }
};
