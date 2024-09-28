import logging
import os
from io import StringIO
from logging import Logger
from typing import List, Iterator, Optional, Tuple

import django_rq
from django.core.cache import caches

from django.db.models import F
from django.db.models.functions import ExtractHour
from django.shortcuts import resolve_url
from notifications.signals import notify

from common.models import Task, Submit, SourcePath, Class

ALLOWED_EXTENSIONS = frozenset(
    (
        "asm",
        "c",
        "h",
        "rs",
        "cpp",
        "cxx",
        "c++",
        "cc",
        "hpp",
        "java",
        "py",
        "cs",
    )
)


def is_ext_allowed(path: str) -> bool:
    return path.split(".")[-1].lower() in ALLOWED_EXTENSIONS


MAX_FILE_SIZE = 128 * 1024


def check_file_size(path: str) -> bool:
    return 0 < os.path.getsize(path) <= MAX_FILE_SIZE


def is_source_valid(logger: Logger, source: SourcePath) -> bool:
    if not is_ext_allowed(source.virt):
        logger.warning(f"Skipping file {source.virt} because of extension")
        return False
    if not check_file_size(source.phys):
        logger.warning(f"Skipping file {source.phys} because of file size")
        return False
    return True


def get_linked_tasks(task_id: int) -> List[Task]:
    task = Task.objects.get(pk=task_id)
    tasks = [task]
    if task.plagiarism_key is not None and task.plagiarism_key.strip() != "":
        tasks = Task.objects.filter(
            subject__id=task.subject.id, plagiarism_key=task.plagiarism_key
        ).order_by("-id")
    return list(tasks)


def get_relevant_submits(task_id: int) -> List[Submit]:
    """
    Find all submits that should be checked for plagiarism for this given task.
    It will return both submits of the task with the given `task_id` and also from other
    tasks that have the same `plagiarism_key` and are for the same subject.
    """
    tasks = get_linked_tasks(task_id)

    submits = (
        Submit.objects.filter(assignment__task__in=tasks)
        .annotate(
            year=F("assignment__clazz__semester__year"), hour=ExtractHour("assignment__assigned")
        )
        # Order from the newest year (semester), from the earliest hour, and from the latest
        # submit of the student
        .order_by("-year", "hour", "-submit_num")
    )
    return list(submits.all())


def iter_template_files(logger: Logger, task: Task) -> Iterator[str]:
    tpl_path = os.path.join(task.dir(), "template")
    for root, _, files in os.walk(tpl_path):
        for f in files:
            full_path = os.path.join(root, f)
            if is_ext_allowed(f) and check_file_size(full_path):
                logger.info(f"Task {task.id}: adding base file {f}")
                yield full_path
            else:
                logger.warning(f"Skipping template file {full_path}")


def iter_submits_per_student(
    submits: List[Submit], limit: Optional[int] = None
) -> Iterator[Submit]:
    """
    Iterate submits so that only the latest submit per student is returned.
    """
    processed = set()
    for submit in submits:
        if submit.student_id not in processed:
            yield submit
            processed.add(submit.student_id)
            if limit is not None and len(processed) >= limit:
                break


def create_stream_logger(name: str, task_id: int) -> Tuple[StringIO, Logger]:
    log_stream = StringIO()
    log_handler = logging.StreamHandler(log_stream)
    log_handler.setFormatter(
        logging.Formatter(f"Task {task_id}: %(asctime)s - %(levelname)s - %(message)s")
    )

    logger = logging.getLogger(f"{name}-{task_id}")
    logger.addHandler(log_handler)
    logger.setLevel(logging.INFO)
    return (log_stream, logger)


def plagcheck_notify_teacher(task_id: int):
    classes = Class.objects.filter(assignedtask__task_id=task_id).distinct()
    teachers = list(set([c.teacher for c in classes]))
    if not teachers:
        return

    task = Task.objects.get(pk=task_id)
    plagcheck_url = resolve_url("teacher_task_plagiarism", task_id=task_id)

    notify.send(
        sender=teachers[0],
        recipient=teachers,
        verb="plagiarism",
        action_object=task,
        custom_text=f"Plagiarism check of {task.name} finished. See results <a href='{plagcheck_url}'>here</a>.",
        important=True,
    )


def enqueue_plagiarism_check(task_id: int, notify: bool = False, submit_limit: int | None = None):
    from common.plagcheck.dolos import dolos_check_task
    from common.plagcheck.moss import (
        moss_delete_result_from_cache,
        moss_check_task,
        moss_job_cache_key,
    )

    cache = caches["default"]

    # MOSS
    moss_delete_result_from_cache(task_id)
    job = django_rq.enqueue(
        moss_check_task,
        task_id=task_id,
        notify_teacher=notify,
        submit_limit=submit_limit,
        job_timeout=60 * 60,
    )
    cache.set(moss_job_cache_key(task_id), job.id, timeout=60 * 60 * 8)

    # Dolos
    django_rq.enqueue(dolos_check_task, task_id=task_id, job_timeout=60 * 60)
