from django import template
from django.template.defaultfilters import stringfilter
from web.task_utils import process_markdown

register = template.Library()

@register.filter()
@stringfilter
def markdown(value, task_code):
    if value:
        return process_markdown(task_code, value)
    return ""
