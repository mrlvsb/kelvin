import os
import re
import hashlib
import subprocess

import lxml.html as html
import lxml

from django.urls import reverse
from django.core.cache import caches

from kelvin.settings import BASE_DIR


class Readme:
    def __init__(self, name, announce, content, meta=None):
        self.name = name
        self.announce = announce
        self.content = content
        self.meta = meta if meta else {}

    def __str__(self):
        return self.content

def load_readme(task_code):
    try:
        task_dir = os.path.join(BASE_DIR, "tasks", task_code)
        readmes = [f for f in os.listdir(task_dir) if f.lower() == "readme.md"]
        if not readmes:
            return

        with open(os.path.join(task_dir, readmes[0])) as f:
            return process_markdown(task_code, f.read())
    except FileNotFoundError:
        pass

def process_markdown(task_code, markdown):
    h = hashlib.md5()
    h.update(markdown.encode('utf-8'))
    key = 'markdown_' + h.hexdigest()

    out = caches['default'].get(key)
    if out:
        return out

    meta = {}
    meta_match = re.match(r'^\s*---\s*(.*?)\n---\s*\n', markdown, re.DOTALL)
    if meta_match:
        for line in meta_match.group(1).splitlines():
            k, v = map(str.strip, line.split(':', 1))
            meta[k] = v

    p = subprocess.Popen(["pandoc"], stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    out = p.communicate(input=markdown.encode('utf-8'))
    out = out[0].decode('utf-8')

    try:
        root = html.fromstring(out)
    except lxml.etree.ParserError as e:
        if str(e) == "Document is empty":
            root = html.fromstring("<p></p>")
        else:
            raise e
    header = root.cssselect('h1')
    name = ""
    announce = ""
    if header:
        name = str(header[0].text)

        if header[0].getparent().tag == 'body':
            root = lxml.etree.Element("p")
        else:
            header[0].getparent().remove(header[0])

    rules = [
        ('a', 'href'),
        ('img', 'src'),
        ('video', 'src'),
        ('source', 'src'),
        ('asciinema-player', 'src'),
    ]

    for tag, attr in rules:
        for el in root.iter(tag):
            if attr in el.attrib and not el.attrib[attr].startswith('http'):
                el.attrib[attr] = reverse('task_asset', args=[task_code, el.attrib[attr]])

    tag = root.cssselect('.announce')
    if tag:
        announce = html.tostring(tag[0], pretty_print=True).decode('utf-8')

    content = html.tostring(root, pretty_print=True).decode('utf-8')
    task_readme = Readme(name, announce, content, meta)
    caches['default'].set(key, task_readme)
    return task_readme
