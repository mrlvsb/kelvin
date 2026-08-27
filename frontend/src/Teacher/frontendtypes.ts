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
    task_type: string | null;
    students: Record<string, AssignmentStudent>;
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
    points: null | number;
    max_points: null | number;
    assigned_points: number | null;
    accepted_submit_num: number;
    accepted_submit_id: number;
    has_final_submit?: boolean;
    color: string;
    link: string; // URL
}

export interface Quiz {
    quiz_id: number;
    quiz_link: string; // URL
    quiz_edit_link: string; // URL
    assigned_id: number;
    name: string;
    name_lower: string;
    assigned: string | Date; // datetime
    deadline: string | Date; // datetime
    max_points: number;
    students: Record<string, QuizStudent>;
}

export interface QuizStudent {
    student: string; // login
    score: number | null;
    scoring_link?: string; // URL
    max_points: number;
    color?: string;
    submitted: boolean;
    submitted_at: string | null;
}

export interface Class {
    id: number;
    teacher_username: string;
    timeslot: string;
    code: string;
    subject_abbr: string;
    room: string | null;
    csv_link: string; // URL
    assignments: Assignment[];
    quizzes: Quiz[];
    summary: string;
    students: StudentIdentity[];
}

export type ClassName = string;

export interface Teacher {
    [login: string]: ClassName[];
}

export interface ClassesByTeacher {
    [abbrev: string]: Teacher;
}

export interface Classes {
    [semester: string]: ClassesByTeacher[];
}
