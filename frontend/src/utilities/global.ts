import { getFromAPI } from './api';

export interface Semester {
    begin: string | Date;
    year: number;
    winter: boolean;
    abbr: string;
    inbus_semester: number;
}

export interface User {
    id: number;
    username: string;
    name: string;
    teacher: boolean;
    is_superuser: boolean;
    is_staff: boolean;
}

export interface APIInfoResponse {
    semester: Semester;
    user: User;
}

/**
 * Fetch the current user and semester from /api/info.
 *
 * Not cached: call this once at the root of a page's component tree and pass the
 * result down via props.
 */
export const loadInfo = async (): Promise<APIInfoResponse> => {
    const data = await getFromAPI<APIInfoResponse>('/api/info');
    if (!data) {
        throw new Error('Failed to load /api/info');
    }

    const begin = new Date(data.semester.begin);
    begin.setHours(0);
    data.semester.begin = begin;

    return data;
};
