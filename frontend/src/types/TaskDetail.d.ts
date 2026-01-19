export type Comment = {
    id: number;
    type: string;
    text?: string;
    author?: string;
    can_edit?: boolean;
    unread?: boolean;
    author_id?: number;
    notification_id?: number;
    meta?: {
        review?: {
            id: number;
            state: 'PENDING' | 'ACCEPTED' | 'REJECTED';
            rating?: number;
        };
        url?: string;
    };
    line?: number | null;
    source?: string;
};

export type Source = {
    path: string;
    type: string;
    content?: string | null;
    content_url?: string;
    comments?: Record<string, Comment[]>;
    error?: string;
    src?: string;
    sources?: string[];
};

export type Submit = {
    num: number;
    submitted: number | string;
    points: number | null;
    comments: number;
    ip_address?: string | null;
};
