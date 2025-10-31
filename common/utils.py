from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.http.response import Http404
from django.utils import timezone

from .inbus import inbus
import django.contrib.auth.models
import re
from functools import lru_cache
from ipware import get_client_ip
from typing import NewType

IPAddressString = NewType("IPAddressString", str)


@lru_cache()
def is_teacher(user):
    return user.groups.filter(name="teachers").exists()


def points_to_color(points, max_points):
    ratio = max(0, min(1, points / max_points))
    green = int(ratio * 200)
    red = int((1 - ratio) * 255)
    return f"#{red:02X}{green:02X}00"


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


def inbus_search_user(login: str) -> inbus.dto.PersonSimple | None:
    return inbus.search_user(login)


def user_from_inbus_person(person: inbus.dto.PersonSimple) -> django.contrib.auth.models.User:
    """
    Returns a Django user from provided person info.

    NOTE: `username` is not set and has to be provided later on.
    """
    user = django.contrib.auth.models.User(
        first_name=person.first_name, last_name=person.second_name, email=person.email
    )

    return user


def user_from_login(login: str) -> django.contrib.auth.models.User | None:
    """
    A shotcut to calling `inbus_search_user` and `user_from_inbus_person`.
    No need to further set anything.
    """
    person = inbus_search_user(login)
    if not person:
        return None
    user = user_from_inbus_person(person)
    user.username = login.upper()
    user.save()

    return user


def get_client_ip_address(request: HttpRequest) -> IPAddressString | None:
    """
    Returns client IP address from HttpRequest instance.
    Returns None if no client IP address is available.
    """
    client_ip, is_routable = get_client_ip(request)

    if client_ip is None:
        return None
    else:
        return IPAddressString(client_ip)


def ip_address_check(function):
    """
    Decorator that restricts access to specific IP addresses.

    The decorated function must have the following parameters:
        - request
        - assignment_id

    Access is granted if any of the following conditions are met:
        - requesting user is a teacher
        - assignment deadline has passed
        - assignment has no IP address restrictions
        - user is accessing from an allowed IP address

    IP address check is performed using:
        models.AssignedTask.is_allowed_from_ip(str)
    """

    def wrapper(*args, **kwargs):
        # this import is here to prevent cyclic dependency (.models uses is_teacher)
        from .models import AssignedTask

        request = args[0]

        if is_teacher(request.user):
            return function(*args, **kwargs)

        assignment_id = kwargs.get("assignment_id")

        try:
            assignment = AssignedTask.objects.get(pk=assignment_id)
        except AssignedTask.DoesNotExist:
            raise Http404(f"AssignedTask with id {assignment_id} not found")

        # allow after deadline
        if assignment.deadline is not None and timezone.now() > assignment.deadline:
            return function(*args, **kwargs)

        if assignment.allowed_classrooms:
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                ip = x_forwarded_for.split(",")[0].strip()
            else:
                ip = request.META.get("REMOTE_ADDR")

            if assignment.is_allowed_from_ip(ip):
                return function(*args, **kwargs)
            else:
                raise PermissionDenied("Access from this IP is not allowed")

    return wrapper
