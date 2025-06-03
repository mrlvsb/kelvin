export interface Assignment {
    task_id: number;
    task_link: string; // URL
    assignment_id: number;
    name: string;
    short_name: string;
    plagcheck_link: string; // URL
    sources_link: string; // URL
    csv_link: string; // URL
    assigned: string | Date; // datetime
    deadline: string | Date; // datetime
    max_points: number;
    students: AssignmentStudent[];
}

export interface StudentIdentity {
    username: string;
    first_name: string;
    last_name: string;
}

export interface AssignmentStudent {
    student: string; // login
    submits: number;
    submits_with_assigned_pts: number;
    first_submit_date: string; // datetime
    last_submit_date: string; // datetime
    points: null | unknown;
    max_points: null | unknown;
    assigned_points: number;
    accepted_submit_num: number;
    accepted_submit_id: number;
    color: string;
    link: string; // URL
}

export interface Class {
    id: number;
    teacher_username: string;
    timeslot: string;
    code: string;
    subject_abbr: string;
    csv_link: string; // URL
    assignments: Assignment[];
    summary: string;
    students: StudentIdentity[];
}
