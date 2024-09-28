import dataclasses
import datetime
import glob
import logging
import shutil
import subprocess
import tempfile
from collections import defaultdict
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

logger = logging.getLogger(__name__)

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
    student: str
    combined_file: Path
    submit_date: datetime.datetime


class Builder:
    def __init__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.entries: List[Entry] = []
        self.counters = {lang: 0 for lang in EXTENSION_TO_LANG_MAP.values()}

    def path(self, path: str) -> Path:
        return Path(self.dir.name) / path

    def add_submit(self, submit: Submit):
        sources = [s for s in submit.all_sources() if is_source_valid(logger, s)]
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
        self.entries.append(
            Entry(
                student=submit.student.username,
                combined_file=combined_path,
                submit_date=submit.created_at,
            )
        )

    def detect_language(self) -> str:
        return max(self.counters, key=self.counters.get)

    def build_csv(self) -> Path:
        data = defaultdict(list)
        for entry in self.entries:
            # Files should be relative to the temp dir
            data["filename"].append(str(entry.combined_file.relative_to(self.dir.name)))
            data["full_name"].append(entry.student)
            data["created_at"].append(entry.submit_date.isoformat())

        df = pd.DataFrame(data)

        csv_path = self.path("info.csv")
        df.to_csv(csv_path, index=False)
        return csv_path

    def get_result_dir(self) -> Optional[Path]:
        for path in glob.glob(f"{self.dir.name}/dolos-report-*"):
            return Path(path)
        return None


def combine_files(files: List[Path], target: Path):
    with open(target, "w") as combined:
        for file in files:
            with open(file) as f:
                print(f"// File {file.name}", file=combined)
                combined.write(f.read())


@dataclasses.dataclass
class DolosResultMissing:
    pass


@dataclasses.dataclass
class DolosResultFailed:
    log: str


@dataclasses.dataclass
class DolosResultPresent:
    dir: Path


DolosResult = Union[DolosResultPresent, DolosResultFailed, DolosResultMissing]


def get_result_dir(task: Task) -> Path:
    return Path(BASE_DIR) / task.dir() / ".dolos-results"


def get_error_log_path(task: Task) -> Path:
    return get_result_dir(task) / "error.log"


def get_dolos_result(task: Task) -> DolosResult:
    dir = get_result_dir(task)
    if not dir.is_dir():
        return DolosResultMissing()
    error_log = get_error_log_path(task)
    if error_log.is_file():
        with open(error_log) as f:
            return DolosResultFailed(log=f.read())
    return DolosResultPresent(dir=dir)


def dolos_check_plagiarism(task_id: int):
    task = Task.objects.get(pk=task_id)
    # Remove any previous results
    result_dir = get_result_dir(task)
    shutil.rmtree(result_dir, ignore_errors=True)

    (log_stream, logger) = create_stream_logger("dolos", task_id=task_id)

    builder = Builder()
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
    except BaseException as e:
        logger.exception(e)
        store_error(task, log_stream.getvalue())


@django_rq.job("default", timeout=60 * 15)
def dolos_check_task(task_id: int):
    dolos_check_plagiarism(task_id=task_id)


def store_error(task: Task, log: str):
    path = get_error_log_path(task)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(log)
