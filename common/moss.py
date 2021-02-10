import django_rq
import mosspy
import tempfile
import os
import shutil
import re
import json
import logging
import networkx as nx
import subprocess
from django.contrib.auth.models import User
from django.conf import settings
from django.core.cache import caches
from networkx.drawing.nx_agraph import write_dot

from common.models import Submit

logger = logging.getLogger('moss')


ALLOWED_EXTENSIONS = {
    "c": "c",
    "h": "c",

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
        f"Task {submit.assignment.task_id}: adding student {submit.student.username} file {name} from {file_path}")
    ext = name.split('.')[-1].lower()
    counters[ALLOWED_EXTENSIONS[ext]] += 1
    moss.addFile(file_path, name)


def add_submit(moss: mosspy.Moss, submit: Submit, counters):
    sources = [source for source in submit.all_sources() if is_ext_allowed(source.virt)]
    if not sources:
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
        add_file(moss, submit, filepath, filename, counters)


@django_rq.job('default', timeout=60*15)
def check_task(task_id):
    logger.info(f"Task {task_id} plagiarism checking started")
    counters = {lang: 0 for lang in ALLOWED_EXTENSIONS.values()}

    try:
        submits = Submit.objects.filter(assignment__task__id=task_id).order_by('-submit_num')
        m = mosspy.Moss(settings.MOSS_USERID)
        # do not ignore matches that occur frequently
        m.setIgnoreLimit(10000)

        # group submissions by directory
        m.setDirectoryMode(1)

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
                try:
                    add_submit(m, submit, counters)
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

                caches['default'].set(f'moss.{task_id}', {
                    "url": url,
                    "matches": matches
                }, timeout=60*60*24*90)
        logger.info(f"Task {task_id} plagiarism checking finished, URL: {url}")
    finally:
        caches['default'].delete(f'moss.job.{task_id}')

class MossResult:
    def __init__(self, url, matches, opts):
        self.url = url
        self.matches = matches
        self.opts = opts
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
    cache.set(f"moss.{task_id}.opts", opts)

def moss_task_get_opts(task_id):
    opts = {
        'percent': 50,
        'lines': 10,
        'show_to_students': False,
    }

    return {
        **opts,
        **caches['default'].get(f"moss.{task_id}.opts", {})
    }

def moss_result(task_id, percent=None, lines=None):
    cache = caches['default']

    key = f"moss.{task_id}"
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
        if min(match['first_percent'], match['second_percent']) >= opts['percent'] and int(match['lines']) >= opts['lines']:
            match['first_fullname'] = User.objects.get(username=match['first_login']).get_full_name()
            match['second_fullname'] = User.objects.get(username=match['second_login']).get_full_name()
            matches.append(match)

    return MossResult(cache_entry.get("url"), matches, opts)
