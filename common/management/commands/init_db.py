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
from textwrap import dedent


@dataclass
class FileToCreate:
    name: str
    contents: str


def create_task_files() -> list[FileToCreate]:
    files = []
    file_names = [".taskid", "config.yml", "readme.md"]
    for file_name in file_names:
        contents = ""
        if file_name == "config.yml":
            contents = dedent("""
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

                #async:
                # LLM is module for automatic feedback generation using Large Language Models
                #llm:
                #enabled: false
                #language: cs

                # Override default model and prompt settings
                #model: gpt-3.5-turbo
                #prompt_name: custom_defined_prompt
                """).strip()
        elif file_name == "readme.md":
            contents = dedent("""
                <div class="announce" markdown="1">
                    On Wednesday, your task will appear here. Please prepare by reading Chapter 5.
                </div>

                Your task is to ...
                """).strip()
        files.append(FileToCreate(file_name, contents))
    return files


def create_user(username: str, is_teacher: bool) -> User:
    user, created = User.objects.get_or_create(username=username, email="")
    if created:
        user.set_password("admin")
    if is_teacher:
        teachers_group = Group.objects.get(name="teachers")
        teachers_group.user_set.add(user)
    user.save()
    return user


def create_semester(date: datetime.datetime) -> Semester:
    summer = 1 < date.month < 7

    begin = date.replace(month=2 if summer else 9, day=1)
    end = date.replace(
        month=7 if summer else 1, day=31, year=date.year if summer else date.year + 1
    )

    semester, _ = Semester.objects.get_or_create(
        begin=begin,
        end=end,
        year=date.year,
        winter=not summer,
        active=True,
        inbus_semester_id=date.year % 100
        + 100,  # 100 + 2 last digtis of the year so for 2025 -> 125
    )

    return semester


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


def create_random_class(teacher: User, semester: Semester, subjects: list[Subject]) -> Class:
    code = f"{random.choice(string.ascii_uppercase)}/{''.join(random.choices(string.digits, k=2))}"
    chosen_subject = random.choice(subjects)
    day = random.choice(Class.Day.choices)[0]
    time = datetime.time(hour=random.choice(range(7, 19)), minute=random.choice(range(0, 60, 15)))
    return create_class(code, teacher, semester, chosen_subject, day, time)


def create_task(
    subject: Subject, semester: Semester, name_suffix: int, files_to_create: list[FileToCreate]
) -> Task:
    name = f"Task_{subject.abbr}_{name_suffix}"
    code = "/".join([subject.abbr, str(semester), name.lower()])
    created_task, created = Task.objects.get_or_create(
        name=name,
        code=code,
        subject=subject,
        announce=True,
        plagiarism_key=None,
    )
    if created:
        write_files_for_task(created_task, files_to_create)
        created_task.type = random.choice(Task.TaskType.choices)[0]
        created_task.save()

    return created_task


def assign_task(
    task: Task, clazz: Class, semester: Semester, semester_week_offset: int = 0
) -> AssignedTask:
    assigned_date = semester.begin + datetime.timedelta(weeks=semester_week_offset)
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


def write_files_for_task(task: Task, files: list[FileToCreate]):
    task_base_dir = task.dir()
    os.makedirs(task_base_dir, exist_ok=True)

    for file in files:
        with open(os.path.join(task_base_dir, file.name), "w") as f:
            if file.name == ".taskid":
                file.contents = f"{task.pk}"
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
    NUM_CLASSES = 5  # Num classes to create overall
    MAX_TASKS = 5  # Max tasks to assign for each class
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
                    "".join(random.choices(string.digits, k=4)),
                )
                for _ in range(self.NUM_STUDENTS)
            ]
        ]

        date = datetime.datetime.now(tz=timezone.utc)
        semester = create_semester(date)
        subjects = [create_subject(name, abbr) for (name, abbr) in self.SUBJECTS]
        task_files = create_task_files()

        for i in range(self.NUM_CLASSES):
            created_class = create_random_class(teacher, semester, subjects)

            created_class.students.add(
                *random.sample(students, k=random.randint(1, self.NUM_STUDENTS))
            )
            for i in range(random.randint(1, self.MAX_TASKS)):
                created_task = create_task(created_class.subject, semester, i, task_files)
                _ = assign_task(created_task, created_class, semester, i)

        logging.info(
            f"Seeding complete\nCreated user with username '{username}' and password 'admin'"
        )
