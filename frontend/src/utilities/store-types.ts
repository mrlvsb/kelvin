export interface FileEntry {
    name?: string;
    type: 'file' | 'dir';
    hide_tab?: boolean;
    content?: string;
    files?: Record<string, FileEntry>;
}

export interface User {
    id: number;
    username: string;
    name: string;
    teacher: boolean;
    is_superuser: boolean;
    is_staff: boolean;
}

export interface Semester {
    begin: Date;
    year: number;
    winter: boolean;
    abbr: string;
    inbus_semester_id: number;
}
