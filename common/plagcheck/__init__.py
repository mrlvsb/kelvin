import os
from logging import Logger
from typing import List, Iterator, Optional

from django.db.models import F
from django.db.models.functions import ExtractHour

from common.models import Task, Submit, SourcePath


ALLOWED_EXTENSIONS = {
    "asm": "c",
    "c": "c",
    "h": "c",
    "cpp": "cc",
    "cxx": "cc",
    "c++": "cc",
    "cc": "cc",
    "hpp": "cc",
    "java": "java",
    "py": "python",
    "cs": "csharp",
}


def is_ext_allowed(path) -> bool:
    return path.split(".")[-1].lower() in ALLOWED_EXTENSIONS.keys()


MAX_FILE_SIZE = 128 * 1024


def check_file_size(path: str) -> bool:
    return 0 < os.path.getsize(path) <= MAX_FILE_SIZE


def is_source_valid(logger, source: SourcePath) -> bool:
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
