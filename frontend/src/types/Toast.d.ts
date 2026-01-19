export type ToastStatus = 'success' | 'warning' | 'error';

export type ToastOptions = {
    title?: string;
    message: string;
    type?: ToastStatus;
    duration?: number;
};

export type ToastApi = {
    success: (
        title: string,
        message?: string,
        options?: Omit<ToastOptions, 'body' | 'type'>
    ) => void;
    warning: (
        title: string,
        message?: string,
        options?: Omit<ToastOptions, 'body' | 'type'>
    ) => void;
    error: (title: string, message?: string, options?: Omit<ToastOptions, 'body' | 'type'>) => void;
};

declare global {
    interface Window {
        toastApi?: ToastApi;
        showToast?: (options: ToastOptions | string, status?: ToastStatus) => void;
    }
}
