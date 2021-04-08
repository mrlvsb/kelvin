from datetime import timedelta
import re
import ldap
from functools import lru_cache

LDAP_CONNECTION = None

@lru_cache()
def is_teacher(user):
    return user.groups.filter(name='teachers').exists()

def points_to_color(points, max_points):
    ratio = max(0, min(1, points / max_points))
    green = int(ratio * 200)
    red = int((1 - ratio) * 255)
    return f'#{red:02X}{green:02X}00'

def parse_time_interval(text):
    patterns = [
        r"(?P<days>\d+)\s*(d|day|days)",
        r"(?P<minutes>\d+)\s*(m|min|minute|minutes)",
        r"(?P<hours>\d+)\s*(h|hour|hours)",
        r"(?P<weeks>\d+)\s*(w|week|weeks)",
    ]

    parsed = {}
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            parsed = {**parsed, **{k: int(v) for k, v in match.groupdict().items()}}
    return timedelta(**parsed)

def ldap_search_user(login):
    global LDAP_CONNECTION

    def connect():
        global LDAP_CONNECTION
        LDAP_CONNECTION = ldap.ldapobject.ReconnectLDAPObject('ldap://ldap.vsb.cz')

    if not LDAP_CONNECTION:
        connect()

    def get():
        return LDAP_CONNECTION.search_s("", ldap.SCOPE_SUBTREE, f"(cn={login})", ["sn", "givenname", "mail"])

    # TODO: escape needed?
    try:
        res = get()
    except ldap.UNAVAILABLE:
        connect()
        res = get()

    if not res:
        return None

    u = res[0][1]
    return {
        "last_name": u['sn'][0].decode('utf-8'),
        "first_name": u['givenname'][0].decode('utf-8'),
        "email": u['mail'][0].decode('utf-8'),
    }
