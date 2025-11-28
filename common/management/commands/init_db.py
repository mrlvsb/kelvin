from dataclasses import dataclass
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from common.models import Class, Subject, User, Semester, Task, AssignedTask
from django.utils import timezone
import datetime
import os
import random
import string
import logging


def create_user(username: str, is_teacher: bool) -> User:
    user, created = User.objects.get_or_create(username=username, email="")
    if created:
        user.set_password("admin")
    if is_teacher:
        teachers_group = Group.objects.get(name="teachers")
        teachers_group.user_set.add(user)
    user.save()
    return user


def create_semesters(date: datetime, num_semesters: int) -> list[Semester]:
    semesters = []
    for i in range(num_semesters):
        summer = 1 < date.month < 7
        begin = datetime.datetime.strptime(
            f"{date.year}-02-01" if summer else f"{date.year}-10-01", "%Y-%m-%d"
        ).date()
        end = datetime.datetime.strptime(
            f"{date.year}-07-31" if summer else f"{date.year + 1}-01-31", "%Y-%m-%d"
        ).date()
        semester, _ = Semester.objects.get_or_create(
            begin=begin,
            end=end,
            year=f"{date.year}",
            winter=not summer,
            active=i == 0,
            inbus_semester_id=124 + i,
        )
        semesters.append(semester)
        if summer:
            date = date.replace(month=8)
            date = date.replace(year=date.year - 1)
        else:
            date = date.replace(month=3)
    return semesters


def create_subject(name: str, abbr: str) -> Subject:
    subj, _ = Subject.objects.get_or_create(name=name, abbr=abbr)
    return subj


def create_class(
    code: str, teacher: User, semester: Semester, subject: Subject, day: Class.Day, time: datetime
) -> Class:
    created_class, _ = Class.objects.get_or_create(
        code=code, teacher=teacher, semester=semester, subject=subject, day=day, time=time
    )
    return created_class


def create_random_class(teacher: User, semesters: list[Semester], subjects: list[Subject]) -> Class:
    code = f"{random.choice(string.ascii_uppercase)}/{''.join(random.choices(string.digits, k=2))}"
    chosen_semester = random.choice(semesters)
    chosen_subject = random.choice(subjects)
    day = random.choice(Class.Day.choices)[0]
    time = datetime.time(hour=random.choice(range(7, 19)), minute=random.choice(range(0, 60, 15)))
    return create_class(code, teacher, chosen_semester, chosen_subject, day, time)


def create_task(subject: Subject, semester: Semester, name_suffix: int) -> Task:
    name = f"Task_{subject.abbr}_{name_suffix}"
    code = "/".join([subject.abbr, str(semester), name.lower()])
    created_task, _ = Task.objects.get_or_create(
        name=name,
        code=code,
        subject=subject,
        announce=True,
        plagiarism_key=None,
        type=random.choice(Task.TaskType.choices)[0],
    )

    return created_task


def assign_task(task: Task, clazz: Class, semester: Semester) -> AssignedTask:
    assigned_date = semester.begin + datetime.timedelta(
        days=random.randint(0, (semester.end - semester.begin).days)
    )
    assigned_date = datetime.datetime.combine(assigned_date, datetime.time.min)
    assigned_task, _ = AssignedTask.objects.get_or_create(
        task_id=task.pk,
        clazz_id=clazz.pk,
        defaults={
            "assigned": timezone.make_aware(assigned_date),
            "deadline": timezone.make_aware(assigned_date + datetime.timedelta(days=7)),
            "max_points": random.randint(1, 5),
        },
    )

    return assigned_task


@dataclass
class FileToCreate:
    name: str
    contents: str


def create_task_files() -> list[FileToCreate]:
    files = []
    file_names = [".taskid", "config.yaml", "readme.md"]
    for file_name in file_names:
        contents = ""
        if file_name == "config.yaml":
            contents = """
                # https://mrlvsb.github.io/kelvin/teachers-guide/task-configuration/
                # You can also use CTRL+Space for autocompleting
                pipeline:
                # compile submitted source codes
                - type: gcc
                # flags: -Wall -Wextra -g -fsanitize=address -lm -Wno-unused-variable

                # add hints from clang-tidy as comments
                #- type: clang-tidy

                # run tests
                #- type: tests

                # run custom commands
                #- type: run
                #  commands:
                #    - ./main 123 | wc -l

                # automatically assign points from the test results
                #- type: auto_grader

                async:
                # LLM is module for automatic feedback generation using Large Language Models
                llm:
                    enabled: false
                    language: cs

                    # Override default model and prompt settings
                    #model: gpt-3.5-turbo
                    #prompt_name: custom_defined_prompt
                """.strip()
        elif file_name == "readme.md":
            contents = """
                <div class="announce" markdown="1">
                    On Wednesday, your task will appear here. Please prepare by reading Chapter 5.
                </div>

                Your task is to ...
                """.strip()
        files.append(FileToCreate(file_name, contents))
    return files


def write_files_for_task(task: Task, files: list[FileToCreate]):
    task_base_dir = task.dir()
    os.makedirs(task_base_dir, exist_ok=True)

    for file in files:
        with open(os.path.join(task_base_dir, file.name), "a") as f:
            f.write(file.contents)


class Command(BaseCommand):
    SUBJECTS = [
        ("Úvod do Programovaní", "UPR"),
        ("Programovaní v Rustu", "PvR"),
        ("Biologicky Inspirované Algoritmy", "BIA"),
        ("Algoritmy 1", "ALG1"),
        ("Algoritmy 2", "ALG2"),
    ]
    NUM_STUDENTS = 10  # Num students to create overall
    NUM_CLASSES = 10  # Num classes to create overall
    NUM_TASKS = 10  # Num tasks to create for each subject in each semester
    DEFAULT_USERNAME = "teacher"  # Username of the created user

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            help="Sets username for the created teacher",
            default=self.DEFAULT_USERNAME,
        )

    def handle(self, *args, **opts):
        username = opts.get("username") or self.DEFAULT_USERNAME
        logging.info(f"Creating teacher with username {username}")

        teacher = create_user(username, True)
        students = [
            create_user(f"{username}{id}", False)
            for username, id in [
                (
                    "".join(random.choices(string.ascii_uppercase, k=3)),
                    "".join(random.choices(string.digits, k=3)),
                )
                for i in range(self.NUM_STUDENTS)
            ]
        ]

        date = datetime.datetime.now(tz=timezone.utc)
        semesters = create_semesters(date, 4)
        subjects = [create_subject(name, abbr) for (name, abbr) in self.SUBJECTS]
        task_files = create_task_files()
        classes: list[Class] = []

        for i in range(self.NUM_CLASSES):
            created_class = create_random_class(teacher, semesters, subjects)

            created_class.students.add(
                *random.sample(students, k=random.randint(1, self.NUM_STUDENTS))
            )
            classes.append(created_class)

        for semester in semesters:
            classes_from_semester = list(filter(lambda x: x.semester == semester, classes))
            for subject in subjects:
                clasess_with_subject = list(
                    filter(lambda x: x.subject == subject, classes_from_semester)
                )
                tasks: list[Task] = []
                for i in range(self.NUM_TASKS):
                    created_task = create_task(subject, semester, i)
                    tasks.append(created_task)

                for clazz in clasess_with_subject:
                    to_be_assigned_tasks = random.choices(tasks, k=random.randint(0, len(tasks)))
                    for task in to_be_assigned_tasks:
                        _ = assign_task(task, clazz, semester)
                        write_files_for_task(task, task_files)

        logging.info("Seeding complete")
