import os

from django.urls import reverse

from pygments import highlight
from pygments.lexers import CLexer
from pygments.formatters import HtmlFormatter
from pygments.token import Token, Text, STANDARD_TYPES
from django.core.cache import caches
import hashlib
import lxml.html as html
import subprocess

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
        with open(path) as f:
            tokens = CLexer().get_tokens(f.read())
            return HtmlLineFormatter().format(tokens)
    except UnicodeDecodeError:
        return ["-- source code contains binary data --"]
    except FileNotFoundError:
        return ["-- source code not found --"]


def highlight_code(path):
    try:
        with open(path) as f:
            return highlight(f.read(), CLexer(), HtmlFormatter(linenos='table', lineanchors='src', anchorlinenos=True))
    except UnicodeDecodeError:
        return ["-- source code contains binary data --"]
    except FileNotFoundError:
        return ["-- source code not found --"]


class Readme:
    def __init__(self, name, announce, content):
        self.name = name
        self.announce = announce
        self.content = content

    def __str__(self):
        return self.content

def load_readme(task_dir, task_code):
    try:
        with open(os.path.join(task_dir, "readme.md")) as f:
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

    p = subprocess.Popen(["pandoc"], stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    out = p.communicate(input=markdown.encode('utf-8'))
    out = out[0].decode('utf-8')

    root = html.fromstring(out)
    header = root.cssselect('h1')
    name = ""
    announce = ""
    if header:
        name = str(header[0].text)
        header[0].getparent().remove(header[0])

    tag = root.cssselect('.announce')
    if tag:
        announce = html.tostring(tag[0], pretty_print=True).decode('utf-8')

    for tag, attr in [('a', 'href'), ('img', 'src')]:
        for el in root.iter(tag):
            if not el.attrib[attr].startswith('http'):
                el.attrib[attr] = reverse('task_asset', args=[task_code, el.attrib[attr]])

    content = html.tostring(root, pretty_print=True).decode('utf-8')
    task_readme = Readme(name, announce, content)
    caches['default'].set(key, task_readme)
    return task_readme
