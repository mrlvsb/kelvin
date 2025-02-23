import os
import re
import hashlib

import lxml.html as html
import lxml
import markdown

from django.urls import reverse
from django.core.cache import caches
from jinja2 import Environment, FileSystemLoader

from kelvin.settings import BASE_DIR


class ProcessedMarkdown:
    def __init__(self, name: str, content: str , announce: str, meta: dict = None):
        self.name = name
        self.content = content
        # announce is a html message that is displayed before the task starts, if available
        self.announce = announce
        self.meta = meta if meta else {}

    def __str__(self):
        return self.content


def load_readme(task_code, vars=None):
    try:
        task_dir = os.path.join(BASE_DIR, "tasks", task_code)
        readmes = [f for f in os.listdir(task_dir) if f.lower() == "readme.md"]
        if not readmes:
            return

        with open(os.path.join(task_dir, readmes[0])) as f:
            if not vars:
                vars = {}

            template = Environment(loader=FileSystemLoader(task_dir)).from_string(f.read())
            return process_markdown(task_code, template.render(**vars))
    except FileNotFoundError:
        pass


def markdown_to_html(input: str) -> str:
    return markdown.markdown(
        input,
        extensions=[
            # Enable ``` code blocks
            "pymdownx.superfences",
            # Enable parsing Markdown inside HTML tags (<div markdown="1">)
            "md_in_html",
            # Better list handling
            # Allows nested indents to be just 2 spaces
            "mdx_truly_sane_lists",
        ],
        extension_configs={
            "pymdownx.superfences": {
                # Only allow ``` for code blocks
                "disable_indented_code_blocks": True
            }
        },
    )


def process_markdown(asset_dir: str, markdown: str, asset_group: str = 'task'):
    h = hashlib.md5()
    h.update(markdown.encode("utf-8"))
    key = "markdown_" + h.hexdigest()

    out = caches["default"].get(key)
    if out:
        return out

    meta = {}
    meta_match = re.match(r"^\s*---\s*(.*?)\n---\s*\n", markdown, re.DOTALL)
    if meta_match:
        for line in meta_match.group(1).splitlines():
            k, v = map(str.strip, line.split(":", 1))
            meta[k] = v

    out = markdown_to_html(markdown)

    try:
        root = html.fromstring(out)
    except lxml.etree.ParserError as e:
        if str(e) == "Document is empty":
            root = html.fromstring("<p></p>")
        else:
            raise e
    header = root.cssselect("h1")
    name = ""
    announce = ""
    if header:
        name = str(header[0].text)

        if header[0].getparent().tag == "body":
            root = lxml.etree.Element("p")
        else:
            header[0].getparent().remove(header[0])

    rules = [
        ("a", "href"),
        ("img", "src"),
        ("video", "src"),
        ("source", "src"),
        ("asciinema-player", "src"),
    ]

    for tag, attr in rules:
        for el in root.iter(tag):
            dst = el.attrib.get(attr, None)
            if not dst or dst.startswith("http"):
                continue

            parts = dst.split("#", 1)
            if parts[0]:
                el.attrib[attr] = reverse(f"{asset_group}_asset", args=[asset_dir, parts[0]])
            else:
                el.attrib[attr] = ""

            if len(parts) == 2:
                el.attrib[attr] += f"#{parts[1]}"

    tag = root.cssselect(".announce")
    if tag:
        announce = html.tostring(tag[0], pretty_print=True).decode("utf-8")

    content = html.tostring(root, pretty_print=True).decode("utf-8")
    processed_markdown = ProcessedMarkdown(name, content, announce, meta)
    caches["default"].set(key, processed_markdown)

    return processed_markdown
