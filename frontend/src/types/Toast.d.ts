export type ToastStatus = 'success' | 'warning' | 'error';

export type ToastOptions = {
    title?: string;
    message: string;
    type?: ToastStatus;
    duration?: number;
};

export type ToastApi = {
    success: (message: string, options?: Omit<ToastOptions, 'message' | 'type'>) => void;
    warning: (message: string, options?: Omit<ToastOptions, 'message' | 'type'>) => void;
    error: (message: string, options?: Omit<ToastOptions, 'message' | 'type'>) => void;
};
