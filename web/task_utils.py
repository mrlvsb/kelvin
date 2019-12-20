import os

from pygments import highlight
from pygments.lexers import CLexer
from pygments.formatters import HtmlFormatter
import markdown2


def highlight_code(path):
    try:
        with open(path) as f:
            return highlight(f.read(), CLexer(), HtmlFormatter(linenos='table', lineanchors='src', anchorlinenos=True))
    except UnicodeDecodeError:
        return "-- source code contains binary data --"
    except FileNotFoundError:
        return "-- source code not found --"


def render_markdown(task_dir, name):
    try:
        with open(os.path.join(task_dir, "readme.md")) as f:
            text = "\n".join(f.read().splitlines()[1:])
        text = markdown2.markdown(text, extras=["fenced-code-blocks", "tables"])
        text = text.replace('src="figures/', f'src="https://upr.cs.vsb.cz/static/tasks/{name}/figures/')
        return text
    except FileNotFoundError:
        pass
