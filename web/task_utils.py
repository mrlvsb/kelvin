import os

from pygments import highlight
from pygments.lexers import CLexer
from pygments.formatters import HtmlFormatter
from pygments.token import Token, Text, STANDARD_TYPES
import markdown2

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

def render_markdown(task_dir, name):
    try:
        with open(os.path.join(task_dir, "readme.md")) as f:
            text = "\n".join(f.read().splitlines()[1:])
        text = markdown2.markdown(text, extras=["fenced-code-blocks", "tables"])
        text = text.replace('src="figures/', f'src="https://kelvin.cs.vsb.cz/static/tasks/{name}/figures/')
        return text
    except FileNotFoundError:
        pass
