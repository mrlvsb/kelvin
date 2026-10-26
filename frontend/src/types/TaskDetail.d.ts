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

/**
 * Comment data that is sent to the API when a comment is created or updated.
 * If `id` is set, an existing comment is updated, otherwise a new comment is created.
 */
export type CommentModel = {
    id?: number;
    text: string;
    line?: number;
    source?: string;
};

/**
 * Request to save a comment, emitted by the comment components.
 */
export type CommentSavePayload = {
    comment: CommentModel;
    // Called when the comment was saved
    success?: () => void;
    // Called when the comment could not be saved, so that the form can be re-enabled
    error?: () => void;
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

export type SourceFile = {
    source: Source;
    opened: boolean;
};

export type CommentCounts = {
    user: number;
    automated: number;
};

export type SelectedRows = {
    path: string;
    from: number;
    to: number;
};
