from datetime import timedelta
from typing import Optional
from . import inbus
import django.contrib.auth.models
import re
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


def inbus_search_user(login: str) -> Optional[inbus.PersonSimple]:
    return inbus.search_user(login)


def user_from_inbus_person(person: inbus.PersonSimple) -> django.contrib.auth.models.User:
    """
    Returns a Django user from provided person info.

    NOTE: `username` is note set and has to be provided later on.
    """
    user = django.contrib.auth.models.User(first_name=person.first_name, last_name=person.second_name, email=person.email)

    return user
