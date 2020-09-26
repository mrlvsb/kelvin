import os
import re
import hashlib
import subprocess

import lxml.html as html
import lxml

from django.urls import reverse
from django.core.cache import caches

from kelvin.settings import BASE_DIR

from pygments import highlight
from pygments.lexers import guess_lexer_for_filename
from pygments.formatters import HtmlFormatter
from pygments.token import Token, Text, STANDARD_TYPES
from pygments.util import ClassNotFound

escape_html_table = {
    ord('&'): u'&amp;',
    ord('<'): u'&lt;',
    ord('>'): u'&gt;',
    ord('"'): u'&quot;',
    ord("'"): u'&#39;',
}
class HtmlLineFormatter(HtmlFormatter):
    """
    Output as html and wrap each line in a span
    """
    name = 'Html wrap lines'
    aliases = ['htmlline']

    def format(self, tokensource):
      lines = []
      for token, line in self.gen(tokensource):
          lines.append(line)
      return lines

    def gen(self, tokensource): 
        lsep = self.lineseparator
        # for <span style=""> lookup only
        getcls = self.ttype2class.get
        escape_table = escape_html_table

        lspan = ''
        line = ''
        for ttype, value in tokensource:
            cls = self._get_css_class(ttype)
            cspan = cls and '<span class="%s">' % cls or ''
            parts = value.translate(escape_table).split('\n')

            # for all but the last line
            for part in parts[:-1]:
                if line:
                    if lspan != cspan:
                        line += (lspan and '</span>') + cspan + part + \
                                (cspan and '</span>') + lsep
                    else: # both are the same
                        line += part + (lspan and '</span>') + lsep
                    yield 1, line
                    line = ''
                elif part:
                    yield 1, cspan + part + (cspan and '</span>') + lsep
                else:
                    yield 1, lsep
            # for the last line
            if line and parts[-1]:
                if lspan != cspan:
                    line += (lspan and '</span>') + cspan + parts[-1]
                    lspan = cspan
                else:
                    line += parts[-1]
            elif parts[-1]:
                line = cspan + parts[-1]
                lspan = cspan
            # else we neither have to open a new span nor set lspan
        if line:
            yield 1, line + (lspan and '</span>') + lsep

def highlight_code_json(path):
    try:
        if os.path.getsize(path) > 500 * 1024:
            return None, ['-- File too large --']
        with open(path) as f:
            text = f.read()
            try:
                tokens = guess_lexer_for_filename(path, text).get_tokens(text)
                return text, HtmlLineFormatter().format(tokens)
            except ClassNotFound:
                return text, text.splitlines()
    except UnicodeDecodeError:
        return None, ["-- source code contains binary data --"]
    except FileNotFoundError:
        return None, ["-- source code not found --"]

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
