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

@django_rq.job('default', timeout=60*15)
def check_task(task_id):
    extensions = {
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

    logger.info(f"Task {task_id} plagiarism checking started")
    counters = {lang: 0 for lang in extensions.values()}

    def is_ext_allowed(path):
        return path.split('.')[-1].lower() in extensions.keys()

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

        processed = set()
        for submit in submits:
            if submit.student_id not in processed:
                processed.add(submit.student_id)
                for source in submit.all_sources():
                    if is_ext_allowed(source.virt):
                        logger.info(f"Task {task_id}: adding student {submit.student.username} file {source.virt}")
                        ext = source.virt.split('.')[-1].lower()
                        counters[extensions[ext]] += 1
                        m.addFile(source.phys, os.path.join(submit.student.username, source.virt))

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
