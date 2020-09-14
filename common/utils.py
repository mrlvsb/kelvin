from datetime import timedelta
import re
import ldap

LDAP_CONNECTION = None

def is_teacher(user):
    return user.groups.filter(name='teachers').exists()

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
    if not LDAP_CONNECTION:
        LDAP_CONNECTION = ldap.initialize('ldap://ldap.vsb.cz')

    # TODO: escape needed?
    res = LDAP_CONNECTION.search_s("", ldap.SCOPE_SUBTREE, f"(cn={login})", ["sn", "givenname", "mail"])

    if not res:
        return None

    u = res[0][1]
    return {
        "last_name": u['sn'][0].decode('utf-8'),
        "first_name": u['givenname'][0].decode('utf-8'),
        "email": u['mail'][0].decode('utf-8'),
    }
