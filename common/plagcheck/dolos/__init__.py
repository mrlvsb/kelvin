import dataclasses
import datetime
import glob
import logging
import shutil
import subprocess
import tempfile
from collections import defaultdict
from logging import Logger
from pathlib import Path
from typing import List, Union, Optional

import django_rq
import pandas as pd

from kelvin.settings import BASE_DIR
from .. import (
    get_relevant_submits,
    iter_submits_per_student,
    is_source_valid,
    iter_template_files,
    create_stream_logger,
)
from ...models import Submit, Task

EXTENSION_TO_LANG_MAP = {
    "asm": "c",
    "c": "c",
    "h": "c",
    "cpp": "cpp",
    "cxx": "cpp",
    "c++": "cpp",
    "cc": "cpp",
    "hpp": "cpp",
    "java": "java",
    "py": "python",
    "cs": "c-sharp",
    "rs": "rust",
}


@dataclasses.dataclass
class Entry:
    # Login + full name
    student: str
    # Year/lesson
    cohort: str
    combined_file: Path
    submit_date: datetime.datetime


class Builder:
    def __init__(self, logger: Logger):
        self.dir = tempfile.TemporaryDirectory()
        self.entries: List[Entry] = []
        self.counters = {lang: 0 for lang in EXTENSION_TO_LANG_MAP.values()}
        self.logger = logger

    def path(self, path: str) -> Path:
        return Path(self.dir.name) / path

    def add_submit(self, submit: Submit):
        sources = [s for s in submit.all_sources() if is_source_valid(self.logger, s)]
        if not sources:
            return

        login = submit.student.username
        combined_path = self.path(f"{login}.submission")

        files = [Path(source.phys) for source in sources]
        combine_files(files, combined_path)
        for filepath in files:
            ext = filepath.suffix[1:]
            if ext in EXTENSION_TO_LANG_MAP:
                self.counters[EXTENSION_TO_LANG_MAP[ext]] += 1
        self.logger.info(
            f"Adding file {combined_path} ({len(files)} combined) for student {submit.student.username}"
        )

        student_name = f"{submit.student.get_full_name()} ({submit.student.username})"
        clazz = submit.assignment.clazz
        cohort = f"{clazz.code} ({clazz.semester})"
        self.entries.append(
            Entry(
                student=student_name,
                cohort=cohort,
                combined_file=combined_path,
                submit_date=submit.created_at,
            )
        )

    def detect_language(self) -> str:
        return max(self.counters, key=self.counters.get)

    def build_csv(self) -> Optional[Path]:
        if len(self.entries) < 2:
            self.logger.info(f"Not enough files to run Dolos ({len(self.entries)})")
            return None

        data = defaultdict(list)
        for entry in self.entries:
            # Files should be relative to the temp dir
            data["filename"].append(str(entry.combined_file.relative_to(self.dir.name)))
            data["full_name"].append(entry.student)
            data["label"].append(entry.cohort)
            data["created_at"].append(entry.submit_date.isoformat())

        df = pd.DataFrame(data)

        self.logger.info(f"Building CSV with {len(self.entries)} entries")
        csv_path = self.path("info.csv")
        df.to_csv(csv_path, index=False)
        return csv_path

    def get_result_dir(self) -> Optional[Path]:
        for path in glob.glob(f"{self.dir.name}/dolos-report-*"):
            return Path(path)
        return None


def combine_files(files: List[Path], target: Path):
    with open(target, "wb") as combined:
        for file in files:
            with open(file, "rb") as f:
                combined.write(f"// File {file.name}\n".encode("utf8"))
                combined.write(f.read())


@dataclasses.dataclass
class DolosResultMissing:
    pass


@dataclasses.dataclass
class DolosResultFailed:
    pass


@dataclasses.dataclass
class DolosResultPresent:
    dir: Path


DolosResult = Union[DolosResultPresent, DolosResultFailed, DolosResultMissing]


OUTCOME_SUCCESS = "OK"


def get_result_dir(task: Task) -> Path:
    return Path(BASE_DIR) / task.dir() / ".dolos-results"


def get_dolos_log_path(task: Task) -> Path:
    """
    This file contains the log of the check.
    """
    return get_result_dir(task) / "dolos.log"


def outcome_file(task: Task) -> Path:
    """
    This file records the outcome of the check (OK or FAIL).
    """
    return get_result_dir(task) / "result.txt"


def mark_outcome(task: Task, outcome: str):
    path = get_result_dir(task)
    path.mkdir(parents=True, exist_ok=True)
    with open(outcome_file(task), "w") as f:
        f.write(outcome)


def mark_success(task: Task):
    mark_outcome(task, OUTCOME_SUCCESS)


def mark_failure(task: Task):
    mark_outcome(task, "FAIL")


def get_dolos_result(task: Task) -> DolosResult:
    outcome = outcome_file(task)
    if not outcome.is_file():
        return DolosResultMissing()

    try:
        with open(outcome, "r") as f:
            if f.read().strip() == OUTCOME_SUCCESS:
                return DolosResultPresent(dir=get_result_dir(task))
    except IOError as e:
        logging.error(e)
    return DolosResultFailed()


def dolos_check_plagiarism(task_id: int):
    task = Task.objects.get(pk=task_id)
    # Remove any previous results
    result_dir = get_result_dir(task)
    shutil.rmtree(result_dir, ignore_errors=True)

    (log_stream, logger) = create_stream_logger("dolos", task_id=task_id)

    builder = Builder(logger)
    try:
        submits = get_relevant_submits(task_id)
        for submit in iter_submits_per_student(submits):
            try:
                builder.add_submit(submit)
            except IOError as e:
                logger.warning(
                    f"Cannot add submit {submit.id} for student {submit.student.username}: {e}"
                )

        csv_path = builder.build_csv()
        if csv_path is not None:
            name = f"{task.name} ({task.subject.abbr})"
            args = [
                "npx",
                "--yes",
                "-p",
                "tree-sitter-rust",
                "-p",
                "@dodona/dolos",
                "dolos",
                "run",
                str(csv_path),
                "--language",
                builder.detect_language(),
                "--name",
                name,
                "--output-format",
                "csv",
            ]

            templates = [Path(f) for f in iter_template_files(logger, task=task)]
            if len(templates) > 0:
                template_path = builder.path("task.template")
                combine_files(templates, template_path)
                args += ["-i", str(template_path.relative_to(builder.dir.name))]

            logger.info(f"Running Dolos\n{' '.join(args)}")
            output = subprocess.run(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=builder.dir.name
            )
            logger.info(f"Dolos exit code: {output.returncode}")
            logger.info(f"Dolos stdout:\n{output.stdout.decode()}\n")
            logger.info(f"Dolos stderr:\n{output.stderr.decode()}\n")

            tmp_result_dir = builder.get_result_dir()
            if tmp_result_dir is None or output.returncode != 0:
                raise Exception("Dolos execution failed")

            # Copy the result CSV files from the temporary dir to the task dir
            shutil.copytree(tmp_result_dir, result_dir)
            mark_success(task)
    except BaseException as e:
        logger.exception(e)
        mark_failure(task)

    log_contents = log_stream.getvalue()
    store_log(task, log_contents)
    print(log_contents)


@django_rq.job("default", timeout=60 * 15)
def dolos_check_task(task_id: int):
    dolos_check_plagiarism(task_id=task_id)


def store_log(task: Task, log: str):
    path = get_dolos_log_path(task)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(log)
