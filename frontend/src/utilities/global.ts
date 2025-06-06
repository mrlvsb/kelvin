import { getFromAPI } from './api';
import { localStorageStore } from './storage';
export const user = localStorageStore('user', {});
export const semester = localStorageStore('semester', {});

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

getFromAPI<APIInfoResponse>('/api/info')
    //.then(res)
    .then((data) => {
        console.log('data:', data);
        data['semester']['begin'] = new Date(data['semester']['begin']);
        data['semester']['begin'].setHours(0);

        semester.value = data['semester'];
        user.value = data['user'];

        console.log(semester.value);
        console.log(user.value);
    });
