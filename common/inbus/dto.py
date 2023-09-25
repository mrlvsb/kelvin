from dataclasses import dataclass
from typing import NewType, List

import serde

DepartmentId = NewType('DepartmentId', int)
SubjectVersionId = NewType('SubjectVersionId', int)
SubjectVersionSchedule = NewType('SubjectVersionSchedule', List['ConcreteActivity'])
ConcreteActivityId = NewType('ConcreteActivityId', int)


@dataclass
class PersonSimple:
    """
    Info about person provided by DTO from INBUS. Not all attributes are present since we don't need them.
    Attribute names are in PEP-8 convention.
    """
    login: str
    full_name: str
    first_name: str
    second_name: str
    email: str


@serde.serde
@dataclass
class Person:
    personId: int
    login: str
    fullName: str


@dataclass
class Subject:
    subjectId: int
    code: str
    abbrev: str
    title: str
    guarantee: Person


@serde.serde
@dataclass
class SubjectVersion:
    subjectVersionId: int
    subject: Subject
    subjectVersionCompleteCode: str
    guarantee: Person


@serde.serde
@dataclass
class WeekActivity:
    """
    Výskyt aktivity v konkrétním týdnu výuky.
    """

    weekActivityId: int # ID výskytu aktivity v konkrétním týdnu výuky
    weekNumber: int # číslo týdne v semestru
    date: str # datum výskytu aktivity (yyyy-MM-dd)


@serde.serde
@dataclass
class ConcreteActivity:
    """
    Concrete activity in schedule.
    """

    concreteActivityId: int # ID rozvrhové aktivity
    template: str # activityTemplate např. P, P1, C, C1 ...
    order: int # pořadí concreteActivity v rámci activity template, dohromady s activityTemplate pak dává např. P/01, P/02, P1/01, C/01 ...
    subjectVersionId: int # ID verze předmětu
    subjectVersionCompleteCode: str # kód verze předmětu (včetně čísla předmětu)
    subjectId: int # ID předmětu
    subjectAbbrev: str # zkratka předmětu
    subjectTitle: str # název předmětu
    educationTypeId: int # ID typu výuky (přednáška, cvičení, konzultace)
    educationTypeAbbrev: str # zkratka typu výuky
    educationTypeTitle: str # název typu výuky
    semesterId: int # ID semestru
    semesterTypeId: int # ID typu semestru
    semesterTypeAbbrev: str # zkratka typy semestru
    semesterTypeTitle: str # název typu semestru
    academicYearId: int # ID akademického roku
    academicYearTitle: str # název akademického roku
    tutorialCentreId: int # ID konzultačního střediska
    tutorialCentreAbbrev: str # zkratka konzultačního střediska
    tutorialCentreTitle: str # název konzultačního střediska
    educationWeekId: int # ID typu týdne výuky (každý, lichý, sudý, nepravidelně)
    educationWeekTitle: str # název typu týdne výuky
    beginScheduleWindowId: int # ID počáteční výukové jednotky (rozvrhového okna)
    activityDuration: int # délka výuky - počet výukových jednotek následujících po sobě
    beginTime: str # ($date-time) čas začátku výuky (HH:mm:ss)
    endTime: str # ($date-time) čas konce výuky (HH:mm:ss)
    weekDayId: int # ID dne v týdnu
    weekDayAbbrev: str # zkratka dne v týdnu
    weekDayTitle: str # název dne v týdnu
    weekActivities: List[WeekActivity] # seznam výskytů aktivity v konkrétních týdnech výuky (využití při nepravidelné výuce), obsahuje: weekActivityId (Integer), weekNumber (Integer), date (Date)
    roomIds: List[int] # seznam ID místností
    teacherIds: List[int] # seznam ID vyučujících (osob)
    studyGroupIds: List[int] # seznam ID studijních skupin (má význam při rozvrhování na studijní skupiny)

    # Default values are defined here, since INBUS API sometimes does not provide there values
    # and Python need default values at the end of the definition
    roomFullcodes: str = '' # optimalizační předpočítávaný atribut z vazby na místnosti
                            # Emptines may be caused by grouping of activities with other activities.
                            # Typical situation is a lecture shed by different versions of a subject.
    studyGroupCodes: str = '' # optimalizační předpočítávaný atribut z vazby na studijní skupiny
    teacherFullNames: str = '' # optimalizační předpočítávaný atribut z vazby na vyučující
    teacherLogins: str = '' # optimalizační předpočítávaný atribut z vazby na vyučující
    teacherShortNames: str = '' # optimalizační předpočítávaný atribut z vazby na vyučující


    def code(self):
        #NOTE: Here, we assume that all lectures will be combined into one :-)
        if self.educationTypeAbbrev.startswith('P'):
            return f'{self.educationTypeAbbrev}/{self.order:02d}'
        return f'{self.educationTypeAbbrev}/{self.order:02d}/{self.subjectVersionCompleteCode}'


@serde.serde
@dataclass
class StudyRelation:
    """
    Relation of student and university.
    """

    studyRelationId: int # ID studijního vztahu
    personId: int # ID osoby
    login: str # osobní číslo (login)
    fullName: str # celé jméno včetně titulů
    email: str # školní email
    studyCode: str # kód studijního poměru, např.: 2. FEI B IVT en P
    beginDate: str #($date-time) začátek studijního vztahu (yyyy-MM-dd)
    endDate: str #($date-time) konec studijního vztahu (yyyy-MM-dd)
    facultyId: int # ID fakulty (OrgUnit)
    facultyAbbrev: str #zkratka fakulty
    facultyTitle: str #název fakulty
    studyTypeId: int #ID typu studia
    studyTypeCode: str # kód typu studia
    studyTypeTitle: str # název typu studia
    studyFormId: int # ID formy studia
    studyFormCode: str # kód formy studia
    studyFormTitle: str # název formy studia
    studyLanguageId: int # ID jazyka výuky
    studyLanguageCode: str # kód jazyka výuky
    studyLanguageTitle: str # název jazyka výuky
    classYearId: int # ID ročníku
    classYearYear: int # ročník ročníku
    tutorialCentreId: int # ID konzultačního střediska
    tutorialCentreAbbrev: str # zkratka konzultačního střediska
    tutorialCentreTitle: str # název konzultačního střediska
    studyProgrammeId: int # ID studijního programu
    studyProgrammeCode: str # kód studijního programu
    studyProgrammeAbbrev: str # zkratka studijního programu
    studyProgrammeTitle: str # název studijního programu
    firstName: str # křestní jméno
    secondName: str # přijmení
    degreeBefore: str = '' #titul před jménem
    degreeAfter: str = '' # titul za jménem
    studySpecializationId: int = 0 # ID studijní specializace
    studySpecializationCode: str = '' # kód studijní specializace
    studySpecializationAbbrev: str = '' # zkratka studijní specializace
    studySpecializationTitle: str = '' # název studijní specializace
    studyBrancheId: int = 0 # ID studijního oboru
    studyBrancheCode: str = '' # kód studijního oboru
    studyBrancheAbbrev: str = '' # zkratka studijního oboru
    studyBrancheTitle: str = '' # název studijního oboru
