import datetime
import logging
import os
import re
import subprocess
import tempfile
from io import StringIO

import django_rq
import mosspy
import networkx as nx
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import caches
from django.db.models import DurationField, ExpressionWrapper, F
from django.db.models.functions import Now
from django.shortcuts import resolve_url
from networkx.drawing.nx_agraph import write_dot
from notifications.signals import notify

from common.models import AssignedTask, Class, Submit, Task

MAX_FILE_SIZE = 128 * 1024

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

    "cs": "csharp"
}


def is_ext_allowed(path) -> bool:
    return path.split('.')[-1].lower() in ALLOWED_EXTENSIONS.keys()


def check_file_size(path: str) -> bool:
    return 0 < os.path.getsize(path) <= MAX_FILE_SIZE


def is_source_valid(logger, source) -> bool:
    if not is_ext_allowed(source.virt):
        logger.warning(f"Skipping file {source.virt} because of extension")
        return False
    if not check_file_size(source.phys):
        logger.warning(f"Skipping file {source.phys} because of file size")
        return False
    return True


def add_file(logger, moss: mosspy.Moss, file_path: str, name: str, counters):
    logger.info(f"Adding file {name} from {file_path}")
    ext = name.split('.')[-1].lower()
    counters[ALLOWED_EXTENSIONS[ext]] += 1
    moss.addFile(file_path, name)


def add_submit(logger, moss: mosspy.Moss, submit: Submit, counters):
    logger.info(f"Checking submit {submit.id} by {submit.student.username}")
    sources = [source for source in submit.all_sources() if is_source_valid(logger, source)]
    if not sources:
        logger.warning("No files found")
        return

    filenames = set()

    def generate_filename(virt_path):
        name = os.path.basename(virt_path)
        fullname = os.path.join(submit.student.username, name)
        index = 1

        while fullname in filenames:
            fullname = os.path.join(submit.student.username, f"{index}_{name}")
            index += 1
        return fullname

    for source in sources:
        filepath = source.phys
        filename = generate_filename(source.virt)
        filenames.add(filename)
        add_file(logger, moss, filepath, filename, counters)


def is_match_suspicious(match, options) -> bool:
    if min(int(match["first_percent"]), int(match["second_percent"])) >= int(options["percent"]):
        return True
    if int(match["lines"]) >= int(options["lines"]):
        return True
    return False


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
        important=True
    )


@django_rq.job("default", timeout=60 * 15)
def moss_check_task(task_id: int, notify_teacher: bool):
    start_timestamp = datetime.datetime.now()

    log_stream = StringIO()
    log_handler = logging.StreamHandler(log_stream)
    log_handler.setFormatter(
        logging.Formatter(f"Task {task_id}: %(asctime)s - %(levelname)s - %(message)s"))

    logger = logging.getLogger(f"moss-{task_id}")
    logger.addHandler(log_handler)
    logger.setLevel(logging.INFO)

    logger.info(f"Plagiarism checking started")
    counters = {lang: 0 for lang in ALLOWED_EXTENSIONS.values()}

    url = None
    matches = []
    success = True

    try:
        submits = Submit.objects.filter(assignment__task__id=task_id).order_by("-submit_num")
        m = mosspy.Moss(settings.MOSS_USERID)
        # do not ignore matches that occur frequently
        m.setIgnoreLimit(10000)

        # group submissions by directory
        m.setDirectoryMode(1)

        # template files
        tpl_path = os.path.join(submits[0].assignment.task.dir(), "template")
        for root, _, files in os.walk(tpl_path):
            for f in files:
                full_path = os.path.join(root, f)
                if is_ext_allowed(f) and check_file_size(full_path):
                    logger.info(f"Task {task_id}: adding base file {f}")
                    m.addBaseFile(full_path)
                else:
                    logger.warning(f"Skipping template file {full_path}")

        processed = set()
        for submit in submits:
            if submit.student_id not in processed:
                try:
                    add_submit(logger, m, submit, counters)
                    processed.add(submit.student_id)
                except IOError as e:
                    logger.error(
                        f"Cannot add submit {submit.id} by {submit.student.username} to MOSS: {e}")

        detected_lang = max(counters, key=counters.get)
        if counters[detected_lang] > 0:
            m.options["l"] = detected_lang

        logger.info(f"Sending files to Moss: {m.files}")
        url = m.send()
        logger.info(f"Moss returned: {url}")
        with tempfile.NamedTemporaryFile() as out:
            m.saveWebPage(url, out.name)

            with open(out.name) as f:
                regex = r'<TR>' \
                        '<TD><A HREF="(?P<link>[^"]+)">(?P<first_login>[^/]+)/(?P<first_path>.*?) \((?P<first_percent>\d+)%\)</A>' \
                        '\s*<TD><A HREF="[^"]+">(?P<second_login>[^/]+)/(?P<second_path>.*?) \((?P<second_percent>\d+)%\)</A>' \
                        '\s*<TD[^>]+>(?P<lines>\d+)'

                for m in re.finditer(regex, f.read()):
                    d = m.groupdict()
                    d["first_percent"] = int(d['first_percent'])
                    d["second_percent"] = int(d['second_percent'])
                    matches.append(d)
        logger.info(f"Plagiarism checking finished, URL: {url}")
    except BaseException as e:
        logger.exception(e)
        success = False
    finally:
        moss_delete_job_from_cache(task_id)

    caches["default"].set(moss_result_cache_key(task_id), {
        "success": success,
        "url": url,
        "matches": matches,
        "started_at": start_timestamp,
        "finished_at": datetime.datetime.now(),
        "log": log_stream.getvalue()
    }, timeout=60 * 60 * 24 * 90)

    if success and notify_teacher:
        moss_notify_teacher(task_id)


def enqueue_moss_check(task_id: int, notify=False):
    cache = caches['default']
    moss_delete_result_from_cache(task_id)
    job = django_rq.enqueue(moss_check_task, task_id, notify, job_timeout=60 * 60)
    cache.set(moss_job_cache_key(task_id), job.id, timeout=60 * 60 * 8)


def do_periodic_moss_check():
    classes = Class.objects.current_semester()

    min_time_from_deadline = datetime.timedelta(minutes=30)
    max_time_from_deadline = datetime.timedelta(days=7)

    assignments = AssignedTask.objects.filter(
        # active tasks
        clazz__in=classes,
        # that have a deadline
        deadline__isnull=False,
    ).annotate(
        # calculate date diff
        date_diff=ExpressionWrapper(Now() - F("deadline"), output_field=DurationField())
    ).filter(
        # filter tasks with dates that are not too old or too new
        date_diff__gte=min_time_from_deadline,
        date_diff__lte=max_time_from_deadline
    )
    tasks = Task.objects.filter(assignedtask__in=assignments)

    cache = caches["default"]
    for task in tasks:
        if (
            cache.get(moss_result_cache_key(task.id)) is not None or
            cache.get(moss_job_cache_key(task.id)) is not None
        ):
            continue
        logging.info(f"Scheduling MOSS check for {task.id}")
        enqueue_moss_check(task.id, notify=True)


# TODO: setup in code instead of UI (Django scheduler management command)
@django_rq.job("default", timeout=60 * 15)
def periodic_moss_check():
    do_periodic_moss_check()


class MossResult:
    def __init__(self,
                 success: bool, url: str, matches,
                 opts,
                 started_at: datetime.datetime,
                 finished_at: datetime.datetime,
                 log: str):
        self.success = success
        self.url = url
        self.matches = matches
        self.opts = opts
        self.started_at = started_at
        self.finished_at = finished_at
        self.log = log
        self.G = nx.Graph()

        for match in matches:
            percent = max(float(match['first_percent']), float(match['second_percent']))
            self.G.add_edge(
                match['first_login'], match['second_login'],
                percent=percent,
                label=f'{int(percent)}%',
                href=match['link']
            )

    def to_svg(self, anonymize=True, login=None):
        max_percent = 0
        for d in self.matches:
            percent = max(int(d['first_percent']), int(d['second_percent']))
            if percent > max_percent:
                max_percent = percent

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

                G.nodes[login]['style'] = 'filled'
                G.nodes[login]['fillcolor'] = '#f8d7da'

            if anonymize:
                mapping = dict(zip(G, range(len(G))))
                if login in mapping:
                    del mapping[login]

                G = nx.relabel_nodes(G, mapping)
                for _, _, d in G.edges(data=True):
                    d.pop('href')

            write_dot(G, out)
            out.flush()

            graph = subprocess.check_output(["dot", "-T", "svg", out.name]).decode('utf-8')
            return re.sub(r'width="[^"]+" height="[^"]+"', '', graph)


def moss_task_set_opts(task_id, opts):
    cache = caches['default']
    cache.set(f"moss.{task_id}.opts", opts, timeout=60*60*24*90)


def moss_task_get_opts(task_id):
    opts = {
        'percent': 20,
        'lines': 10,
        'show_to_students': False,
    }

    return {
        **opts,
        **caches['default'].get(f"moss.{task_id}.opts", {})
    }


def moss_result(task_id, percent=None, lines=None):
    cache = caches['default']

    key = moss_result_cache_key(task_id)
    cache_entry = cache.get(key)
    if not cache_entry:
        return None

    opts = moss_task_get_opts(task_id)
    if percent:
        opts['percent'] = percent
    if lines:
        opts['lines'] = lines

    matches = []
    for match in cache_entry["matches"]:
        if is_match_suspicious(match, opts):
            match['first_fullname'] = User.objects.get(
                username=match['first_login']).get_full_name()
            match['second_fullname'] = User.objects.get(
                username=match['second_login']).get_full_name()
            matches.append(match)

    return MossResult(
        cache_entry.get("success"),
        cache_entry.get("url"),
        matches,
        opts,
        cache_entry.get("started_at"),
        cache_entry.get("finished_at"),
        cache_entry.get("log")
    )


def moss_result_cache_key(task_id: int) -> str:
    return f"moss.{task_id}"


def moss_job_cache_key(task_id: int) -> str:
    return f"moss.job.{task_id}"


def moss_delete_job_from_cache(task_id: int):
    caches["default"].delete(moss_job_cache_key(task_id))


def moss_delete_result_from_cache(task_id: int):
    caches["default"].delete(moss_result_cache_key(task_id))
