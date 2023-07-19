from datetime import timedelta
from typing import Optional
from .inbus import inbus
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


def inbus_search_user(login: str) -> Optional[inbus.dto.PersonSimple]:
    return inbus.search_user(login)


def user_from_inbus_person(person: inbus.dto.PersonSimple) -> django.contrib.auth.models.User:
    """
    Returns a Django user from provided person info.

    NOTE: `username` is not set and has to be provided later on.
    """
    user = django.contrib.auth.models.User(first_name=person.first_name, last_name=person.second_name, email=person.email)

    return user


def user_from_login(login: str) -> django.contrib.auth.models.User:
    """
    A shotcut to calling `inbus_search_user` and `user_from_inbus_person`.
    No need to further set anything.
    """
    person = inbus_search_user(login)
    user = user_from_inbus_person(person)
    user.username = login.upper()
    user.save()

    return user
