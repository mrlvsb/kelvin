import django_rq
import mosspy
import tempfile
import os
import shutil
import re
import json
import logging
from django.conf import settings
from django.core.cache import caches

from common.models import Submit

logger = logging.getLogger('moss')


ALLOWED_EXTENSIONS = {
    "c": "c",
    "h": "h",

    "cpp": "cc",
    "cxx": "cc",
    "c++": "cc",
    "cc": "cc",
    "hpp": "cc",

    "java": "java",

    "py": "python",
}


def is_ext_allowed(path):
    return path.split('.')[-1].lower() in ALLOWED_EXTENSIONS.keys()


def add_file(moss: mosspy.Moss, submit: Submit, file_path: str, name: str, counters):
    logger.info(
        f"Task {submit.assignment.task_id}: adding student {submit.student.username} file {name}")
    ext = name.split('.')[-1].lower()
    counters[ALLOWED_EXTENSIONS[ext]] += 1
    moss.addFile(file_path, os.path.join(submit.student.username, name))


def merge_submit_files(sources, tmpdir: str) -> str:
    sources = sorted(sources, key=lambda s: s.virt)
    temp_name = next(tempfile._get_candidate_names())
    full_path = os.path.join(tmpdir, temp_name)

    with open(full_path, "w") as f:
        for source in sources:
            f.write(f"// {source.virt}\n")
            with open(source.phys) as source_file:
                for line in source_file:
                    f.write(line)
            f.write("\n")
    return full_path


def add_submit(moss: mosspy.Moss, submit: Submit, tmpdir: str, counters):
    sources = [source for source in submit.all_sources() if is_ext_allowed(source.virt)]
    if not sources:
        return

    if len(sources) == 1:
        add_file(moss, submit, sources[0].phys, sources[0].virt, counters)
    else:
        file_path = merge_submit_files(sources, tmpdir)
        add_file(moss, submit, file_path, sources[0].virt, counters)


@django_rq.job('default', timeout=60*15)
def check_task(task_id):
    logger.info(f"Task {task_id} plagiarism checking started")
    counters = {lang: 0 for lang in ALLOWED_EXTENSIONS.values()}

    try:
        submits = Submit.objects.filter(assignment__task__id=task_id).order_by('-submit_num')
        m = mosspy.Moss(settings.MOSS_USERID)

        # template files
        tpl_path = os.path.join(submits[0].assignment.task.dir(), "template")
        for root, _, files in os.walk(tpl_path):
            for f in files:
                if is_ext_allowed(f):
                    logger.info(f"Task {task_id}: adding base file {f}")
                    m.addBaseFile(os.path.join(root, f))

        with tempfile.TemporaryDirectory(prefix="kelvin_moss") as tmpdir:
            processed = set()
            for submit in submits:
                print(submit.student_id, submit.student.id)
                if submit.student_id not in processed:
                    try:
                        add_submit(m, submit, tmpdir, counters)
                        processed.add(submit.student_id)
                    except IOError:
                        logger.error(f"Cannot add submit {submit.id} to MOSS")

            detected_lang = max(counters, key=counters.get)
            if counters[detected_lang] > 0:
                m.options['l'] = detected_lang

            url = m.send()
            with tempfile.NamedTemporaryFile() as out:
                m.saveWebPage(url, out.name)

                matches = []
                with open(out.name) as f:
                    regex = r'<TR>' \
                        '<TD><A HREF="(?P<link>[^"]+)">(?P<first_login>[^/]+)/(?P<first_path>.*?) \((?P<first_percent>\d+)%\)</A>' \
                        '\s*<TD><A HREF="[^"]+">(?P<second_login>[^/]+)/(?P<second_path>.*?) \((?P<second_percent>\d+)%\)</A>' \
                        '\s*<TD[^>]+>(?P<lines>\d+)'

                    for m in re.finditer(regex, f.read()):
                        d = m.groupdict()
                        d['first_percent'] = int(d['first_percent'])
                        d['second_percent'] = int(d['second_percent'])
                        matches.append(d)

                    caches['default'].set(f'moss.{task_id}', matches, timeout=60*60*24*10)
            logger.info(f"Task {task_id} plagiarism checking finished")
    finally:
        caches['default'].delete(f'moss.job.{task_id}')
