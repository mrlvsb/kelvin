export interface ConcreteActivity {
    /**
    Concrete activity in schedule.
    */
    concreteActivityId: number;
    order: number;
    subjectVersionId: number;
    subjectVersionCompleteCode: string;
    educationTypeAbbrev: string;
    beginTime: string;
    endTime: string;
    weekDayAbbrev: string;
    teacherFullNames?: string;
}

interface InbusSubject {
    subjectId: number;
    code: string;
    abbrev: string;
    title: string;
}

export interface InbusSubjectVersion {
    subjectVersionId: number;
    subject: InbusSubject;
    subjectVersionCompleteCode: string;
}
