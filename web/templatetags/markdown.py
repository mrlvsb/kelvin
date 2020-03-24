from django import template
from django.template.defaultfilters import stringfilter
import markdown2

register = template.Library()

@register.filter()
@stringfilter
def markdown(value):
    return markdown2.markdown(value, extras=["fenced-code-blocks", "tables"])
