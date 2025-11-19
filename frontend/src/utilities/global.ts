import { getFromAPI } from './api';
import { localStorageStore } from './storage';

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

// TODO: cache data with expiry time
export const loadInfo = async (forceDataRefresh = false) => {
    const user = localStorageStore<User | undefined>('user', undefined);
    const semester = localStorageStore<Semester | undefined>('semester', undefined);

    if (!user.value || !semester.value || forceDataRefresh) {
        const data = await getFromAPI<APIInfoResponse>('/api/info');
        console.log('data:', data);
        data['semester']['begin'] = new Date(data['semester']['begin']);
        data['semester']['begin'].setHours(0);

        user.value = data['user'];
        semester.value = data['semester'];
    }

    return [user, semester] as const;
};
