import dataclasses
import datetime
import logging
import os
import re
import subprocess
import tempfile
from io import StringIO
from logging import Logger
from pathlib import Path
from typing import List

import django_rq
import mosspy
import networkx as nx
from django.conf import settings
from django.core.cache import caches
from django.db.models import DurationField, ExpressionWrapper, F
from django.db.models.functions import Now
from django.shortcuts import resolve_url
from django.urls import reverse
from networkx.drawing.nx_agraph import write_dot
from notifications.signals import notify

from common.models import AssignedTask, Class, Submit, Task
from common.plagcheck import (
    get_relevant_submits,
    ALLOWED_EXTENSIONS,
    is_source_valid,
    iter_template_files,
    iter_submits_per_student,
)
from kelvin.settings import BASE_DIR


def add_file(logger, moss: mosspy.Moss, file_path: str, name: str, counters):
    logger.info(f"Adding file {name} from {file_path}")
    ext = name.split(".")[-1].lower()
    if ext in ALLOWED_EXTENSIONS:
        counters[ALLOWED_EXTENSIONS[ext]] += 1
    moss.addFile(file_path, name)


def create_submit_identifier(submit: Submit) -> str:
    """
    Creates an identifier that is used by MOSS to identify a single submission.
    """
    return f"{submit.student.username}-{submit.assignment.id}"


def get_login_and_assignment(identifier: str) -> (str, int):
    """
    Parses MOSS identifier back into login and assignment ID.
    """
    student, assignment = identifier.split("-", maxsplit=2)
    return (student, int(assignment))


def add_submit(logger: Logger, moss: mosspy.Moss, submit: Submit, counters):
    logger.info(f"Checking submit {submit.id} by {submit.student.username}")
    sources = [source for source in submit.all_sources() if is_source_valid(logger, source)]
    if not sources:
        logger.warning("No files found")
        return

    filenames = set()

    def generate_filename(virt_path):
        name = os.path.basename(virt_path)
        identifier = create_submit_identifier(submit)
        fullname = os.path.join(identifier, name)
        index = 1

        while fullname in filenames:
            fullname = os.path.join(identifier, f"{index}_{name}")
            index += 1
        return fullname

    for source in sources:
        filepath = source.phys
        filename = generate_filename(source.virt)
        filenames.add(filename)
        add_file(logger, moss, filepath, filename, counters)


def moss_notify_teacher(task_id: int):
    classes = Class.objects.filter(assignedtask__task_id=task_id).distinct()
    teachers = list(set([c.teacher for c in classes]))
    if not teachers:
        return

    task = Task.objects.get(pk=task_id)
    moss_url = resolve_url("teacher_task_moss_check", task_id=task_id)

    notify.send(
        sender=teachers[0],
        recipient=teachers,
        verb="plagiarism",
        action_object=task,
        custom_text=f"MOSS plagiarism check of {task.name} finished. See results <a href='{moss_url}'>here</a>.",
        important=True,
    )


@dataclasses.dataclass(frozen=True)
class MatchedStudent:
    login: str
    percent: int
    assignment_id: int


@dataclasses.dataclass(frozen=True)
class PlagiarismMatch:
    id: int
    first: MatchedStudent
    second: MatchedStudent
    lines: int
    link: str
    moss_link: str


@dataclasses.dataclass
class MossTaskOptions:
    percent: int
    lines: int
    show_to_students: bool
    # New attributes below this line must provide a default value!


def is_match_suspicious(match: PlagiarismMatch, options: MossTaskOptions) -> bool:
    if min(match.first.percent, match.second.percent) >= options.percent:
        return True
    if match.lines >= options.lines:
        return True
    return False


def get_match_local_dir(task: Task, match: PlagiarismMatch) -> Path:
    """
    Returns a path on the local filesystem that wil be used to store the match result.
    """
    directory = Path(BASE_DIR) / task.dir() / ".moss-results"
    id = f"{match.first.login}-{match.first.assignment_id}_{match.second.login}-{match.second.assignment_id}"
    return directory / id


@django_rq.job("default", timeout=60 * 15)
def moss_check_task(task_id: int, notify_teacher: bool, submit_limit: int | None):
    start_timestamp = datetime.datetime.now()

    log_stream = StringIO()
    log_handler = logging.StreamHandler(log_stream)
    log_handler.setFormatter(
        logging.Formatter(f"Task {task_id}: %(asctime)s - %(levelname)s - %(message)s")
    )

    logger = logging.getLogger(f"moss-{task_id}")
    logger.addHandler(log_handler)
    logger.setLevel(logging.INFO)

    logger.info("Plagiarism checking started")
    counters = {lang: 0 for lang in ALLOWED_EXTENSIONS.values()}

    url = None
    matches = []
    success = True

    try:
        submits = get_relevant_submits(task_id)
        if not submits:
            return

        moss_client = mosspy.Moss(settings.MOSS_USERID)
        # do not ignore matches that occur frequently
        moss_client.setIgnoreLimit(10000)

        # group submissions by directory
        moss_client.setDirectoryMode(1)

        # template files
        for path in iter_template_files(logger, submits[0].assignment.task):
            moss_client.addBaseFile(path)

        handled_submits = 0
        for submit in iter_submits_per_student(submits, limit=submit_limit):
            try:
                add_submit(logger, moss_client, submit, counters)
                handled_submits += 1
            except IOError as e:
                logger.error(
                    f"Cannot add submit {submit.id} by {submit.student.username} to MOSS: {e}"
                )

        detected_lang = max(counters, key=counters.get)
        if counters[detected_lang] > 0:
            moss_client.options["l"] = detected_lang

        file_bytes = sum(os.path.getsize(file_path) for (file_path, _) in moss_client.files)
        logger.info(
            f"Sending {handled_submits} submit(s), {len(moss_client.files)} file(s), {file_bytes} bytes to Moss"
        )
        url = moss_client.send()
        logger.info(f"Moss returned: {url}")
        with tempfile.NamedTemporaryFile() as out:
            moss_client.saveWebPage(url, out.name)

            with open(out.name) as f:
                regex = (
                    r"<TR>"
                    r'<TD><A HREF="(?P<link>[^"]+)">(?P<first_id>[^/]+)/(?P<first_path>.*?) \((?P<first_percent>\d+)%\)</A>'
                    r'\s*<TD><A HREF="[^"]+">(?P<second_id>[^/]+)/(?P<second_path>.*?) \((?P<second_percent>\d+)%\)</A>'
                    r"\s*<TD[^>]+>(?P<lines>\d+)"
                )

                for moss_client in re.finditer(regex, f.read()):
                    d = moss_client.groupdict()
                    (first_login, first_assignment) = get_login_and_assignment(d["first_id"])
                    (second_login, second_assignment) = get_login_and_assignment(d["second_id"])

                    moss_link = d["link"]
                    match_id = len(matches)
                    match = PlagiarismMatch(
                        id=match_id,
                        first=MatchedStudent(
                            percent=int(d["first_percent"]),
                            login=first_login,
                            assignment_id=first_assignment,
                        ),
                        second=MatchedStudent(
                            percent=int(d["second_percent"]),
                            login=second_login,
                            assignment_id=second_assignment,
                        ),
                        lines=int(d["lines"]),
                        link=reverse(
                            "teacher_task_moss_result",
                            kwargs=dict(task_id=task_id, match_id=match_id, path="index.html"),
                        ),
                        moss_link=moss_link,
                    )

                    matches.append(match)
        logger.info(f"Plagiarism checking finished, URL: {url}")
    except BaseException as e:
        logger.exception(e)
        success = False
    finally:
        moss_delete_job_from_cache(task_id)

    caches["default"].set(
        moss_result_cache_key(task_id),
        {
            "success": success,
            "url": url,
            "matches": matches,
            "started_at": start_timestamp,
            "finished_at": datetime.datetime.now(),
            "log": log_stream.getvalue(),
        },
        timeout=60 * 60 * 24 * 90,
    )

    if success and notify_teacher:
        moss_notify_teacher(task_id)


def enqueue_moss_check(task_id: int, notify: bool = False, submit_limit: int | None = None):
    cache = caches["default"]
    moss_delete_result_from_cache(task_id)
    job = django_rq.enqueue(
        moss_check_task,
        task_id=task_id,
        notify_teacher=notify,
        submit_limit=submit_limit,
        job_timeout=60 * 60,
    )
    cache.set(moss_job_cache_key(task_id), job.id, timeout=60 * 60 * 8)


def do_periodic_moss_check():
    classes = Class.objects.current_semester()

    min_time_from_deadline = datetime.timedelta(minutes=30)
    max_time_from_deadline = datetime.timedelta(days=7)

    assignments = (
        AssignedTask.objects.filter(
            # active tasks
            clazz__in=classes,
            # that have a deadline
            deadline__isnull=False,
        )
        .annotate(
            # calculate date diff
            date_diff=ExpressionWrapper(Now() - F("deadline"), output_field=DurationField())
        )
        .filter(
            # filter tasks with dates that are not too old or too new
            date_diff__gte=min_time_from_deadline,
            date_diff__lte=max_time_from_deadline,
        )
    )
    tasks = Task.objects.filter(assignedtask__in=assignments)

    cache = caches["default"]
    for task in tasks:
        if (
            cache.get(moss_result_cache_key(task.id)) is not None
            or cache.get(moss_job_cache_key(task.id)) is not None
        ):
            continue
        logging.info(f"Scheduling MOSS check for {task.id}")
        enqueue_moss_check(task.id, notify=True)


# TODO: setup in code instead of UI (Django scheduler management command)
@django_rq.job("default", timeout=60 * 15)
def periodic_moss_check():
    do_periodic_moss_check()


class MossResult:
    def __init__(
        self,
        success: bool,
        url: str,
        matches: List[PlagiarismMatch],
        opts: MossTaskOptions,
        started_at: datetime.datetime,
        finished_at: datetime.datetime,
        log: str,
    ):
        self.success = success
        self.url = url
        self.matches = matches
        self.opts = opts
        self.started_at = started_at
        self.finished_at = finished_at
        self.log = log
        self.G = nx.Graph()

        for match in matches:
            percent = max(float(match.first.percent), float(match.second.percent))
            self.G.add_edge(
                match.first.login,
                match.second.login,
                percent=percent,
                label=f"{int(percent)}%",
                href=match.link,
            )

    def to_svg(self, anonymize=True, login=None):
        with tempfile.NamedTemporaryFile("w") as out:
            G = self.G.copy()

            def get_component():
                for component in nx.connected_components(G):
                    if login in component:
                        return G.subgraph(component).copy()
                return None

            if login:
                G = get_component()
                if not G:
                    return None

                G.nodes[login]["style"] = "filled"
                G.nodes[login]["fillcolor"] = "#f8d7da"

            if anonymize:
                mapping = dict(zip(G, range(len(G))))
                if login in mapping:
                    del mapping[login]

                G = nx.relabel_nodes(G, mapping)
                for _, _, match in G.edges(data=True):
                    match.pop("href")

            write_dot(G, out)
            out.flush()

            graph = subprocess.check_output(["dot", "-T", "svg", out.name]).decode("utf-8")
            return re.sub(r'width="[^"]+" height="[^"]+"', "", graph)


def moss_task_set_opts(task_id: int, opts: MossTaskOptions):
    cache = caches["default"]
    cache.set(f"moss.{task_id}.opts", dataclasses.asdict(opts), timeout=60 * 60 * 24 * 90)


def moss_task_get_opts(task_id: int) -> MossTaskOptions:
    opts = MossTaskOptions(
        percent=20,
        lines=10,
        show_to_students=False,
    )

    saved_opts = caches["default"].get(f"moss.{task_id}.opts", {})
    opts_dict = dataclasses.asdict(opts)
    opts_dict.update(saved_opts)
    return MossTaskOptions(**opts_dict)


def moss_result(
    task_id: int, percent: int | None = None, lines: int | None = None, filtered: bool = True
) -> MossResult | None:
    """
    If `filtered` is True, matches will be filtered according to saved or passed filter options.
    """

    cache = caches["default"]

    key = moss_result_cache_key(task_id)
    cache_entry = cache.get(key)
    if not cache_entry:
        return None

    opts = moss_task_get_opts(task_id)
    if percent:
        opts.percent = percent
    if lines:
        opts.lines = lines

    matches = []
    for match in cache_entry.get("matches", []):
        if (not filtered) or is_match_suspicious(match, opts):
            matches.append(match)

    return MossResult(
        cache_entry.get("success"),
        cache_entry.get("url"),
        matches,
        opts,
        cache_entry.get("started_at"),
        cache_entry.get("finished_at"),
        cache_entry.get("log"),
    )


def moss_result_cache_key(task_id: int) -> str:
    return f"moss.{task_id}"


def moss_job_cache_key(task_id: int) -> str:
    return f"moss.job.{task_id}"


def moss_delete_job_from_cache(task_id: int):
    caches["default"].delete(moss_job_cache_key(task_id))


def moss_delete_result_from_cache(task_id: int):
    caches["default"].delete(moss_result_cache_key(task_id))
