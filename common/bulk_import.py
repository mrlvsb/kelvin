import datetime
from .inbus import inbus
from common.utils import is_teacher, user_from_login
import serde
from dataclasses import dataclass
from django.contrib.auth.models import User, Group
from common.models import Class, Semester, Subject
from typing import List, Dict, Generator
import traceback

from .inbus.dto import ConcreteActivity, ConcreteActivityId


class ImportException(Exception):
    pass


@serde.serde
@dataclass
class ImportResult:
    login: str
    firstname: str
    lastname: str
    created: bool


def run(
    concrete_activities: List[ConcreteActivity],
    subject_abbr: str,
    semester: Semester,
    user: User,
    activities_to_teacher: Dict[int, str],
) -> Generator[ImportResult, None, None]:
    """
    `subject_addr`: subject abbreviation from selected subject in UI
    `user`: importing user (the that uses import UI)
    `activities_to_teacher`: dictionary of activities and manually assigned teachers (username) in the UI
    """

    try:
        subject = Subject.objects.get(abbr=subject_abbr)
    except Subject.DoesNotExist:
        raise ImportException(f"Subject {subject_abbr} does not exist. Please create it first.")

    # Create classes in DB

    class_in_db = {}
    for ca in concrete_activities:
        c = ca.code()
        try:
            class_in_db[c] = Class.objects.get(code=c, semester=semester, subject=subject)
        except Class.DoesNotExist:
            class_in_db[c] = Class()
            class_in_db[c].code = c
            day = ca.weekDayAbbrev.upper()
            mapping = {"ÚT": "UT", "ČT": "CT", "PÁ": "PA"}
            class_in_db[c].day = mapping.get(day, day)
            class_in_db[c].hour = ca.beginTime
            class_in_db[c].year = datetime.datetime.now().year
            class_in_db[c].winter = semester.winter  # or ca.semesterTypeId == 1
            class_in_db[c].time = ca.beginTime
            class_in_db[c].subject = subject
            class_in_db[c].semester = semester

            # Teacher
            # TODO: There may be more teachers for a class
            if len(ca.teacherIds) > 1:
                # if there are more than 1 teacher, assign class to the one, who's importing
                teacher = User.objects.get(username=user.username.upper())
            elif len(ca.teacherIds) == 1:
                try:
                    teacher = User.objects.get(username=ca.teacherLogins.upper())
                except User.DoesNotExist:
                    teacher = user_from_login(ca.teacherLogins.upper())
                    if not teacher:
                        raise ImportException(
                            f"Cannot create user {ca.teacherLogins.upper()}.\n\nTraceback\n\n{traceback.format_exc()}"
                        )
            else:
                # We assign all activities without teacher in INBUS to the one selected by importing user
                try:
                    teacher_username = activities_to_teacher[ca.concreteActivityId]
                    teacher = User.objects.get(username=teacher_username)
                except KeyError:
                    msg = f"There's no assigned teacher to activity {ca.code()}. Please, make sure you selected one."
                    raise ImportException(msg)

            if not is_teacher(teacher):
                teachers_group = Group.objects.get_by_natural_key("teachers")
                teacher.groups.add(teachers_group)

            class_in_db[c].teacher = teacher

            class_in_db[c].save()

        # Students
        students_in_class = inbus.students_in_concrete_activity(
            ConcreteActivityId(ca.concreteActivityId)
        )

        for student in students_in_class:
            login = student.login.upper()
            firstname, lastname = student.firstName, student.secondName

            created = False

            student_user = None
            try:
                student_user = User.objects.get(username=login)
            except User.DoesNotExist:
                student_user = user_from_login(login)
                created = True

            class_in_db[c].students.add(student_user)

            yield ImportResult(login, firstname, lastname, created)
