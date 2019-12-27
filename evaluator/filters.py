import re

class LowerFilter:
    def filter(self, s):
        return s.lower()

class TrailingSpacesFilter:
    def filter(self, s):
        s = re.sub(r'^\s+', '', s, flags=re.MULTILINE)
        s = re.sub(r'\s+$', '', s, flags=re.MULTILINE)
        return s

class AllSpacesFilter:
    def filter(self, s):
        s = re.sub(r'\s+', ' ', s, flags=re.MULTILINE)
        return s.strip()

class StripFilter:
    def filter(self, s):
        return s.strip()

class RStripFilter:
    def filter(self, s):
        return s.rstrip()

class LStripFilter:
    def filter(self, s):
        return s.lstrip()

all_filters = {
    'lower': LowerFilter,
    'trailingspaces': TrailingSpacesFilter,
    'allspaces': AllSpacesFilter,
    'strip': StripFilter,
    'rstrip': RStripFilter,
    'lstrip': LStripFilter,
}

def apply_filters(s, filters):
    for f in filters:
        s = f.filter(s)
    return s
