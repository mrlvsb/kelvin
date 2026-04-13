import io
import re
import tarfile
from datetime import timedelta, datetime
from functools import lru_cache
from typing import NewType

import django.contrib.auth.models
import requests
from django.conf import settings
from django.http import HttpRequest
from ipware import get_client_ip

from .exceptions.http_exceptions import HttpException403
from .inbus import inbus

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
    # Do not allow proxies or custom HTTP headers that can override the IP address
    client_ip, is_routable = get_client_ip(
        request, proxy_count=0, request_header_order=["REMOTE_ADDR"]
    )

    if client_ip is None:
        return None
    else:
        return IPAddressString(client_ip)


def download_source_to_path(source_url: str, destination_path: str) -> None:
    """
    Downloads archived content from source_url and extracts it to destination_path.
    """

    session = requests.Session()
    # Disable SSL verification in DEBUG mode (local Docker development environment).
    #
    # EXPLANATION:
    # In the local Docker development environment (DEBUG=True), the services communicate
    # via internal Docker network names (e.g. 'https://nginx').
    # The Nginx service uses self-signed certificates for HTTPS.
    # Since these certificates are not issued by a trusted Certificate Authority (CA),
    # requests would fail with an SSL error. Disabling verification allows
    # the evaluator to download submissions and upload results in this dev environment.
    if settings.DEBUG:
        session.verify = False

    response = session.get(source_url)

    if response.status_code != 200:
        raise Exception(f"Failed to download source code: {response.status_code}")

    with tarfile.open(fileobj=io.BytesIO(response.content)) as tar:
        tar.extractall(destination_path)


def build_evaluation_download_uri(request, location):
    if settings.EVALUATION_LINK_BASEURL:
        return settings.EVALUATION_LINK_BASEURL + location
    return request.build_absolute_uri(location)


def prohibit_during_test(function):
    """
    Decorator that restricts access to a page if the student has any ongoing exams.

    The decorated function must accept one of the following parameter sets:
    - request and assignment_id, or
    - author

    Use the first option when access to specific test tasks should still be allowed.
    Use the second option to disable all interactions during an ongoing exam.

    Currently:
    - The first option is used for the task page and its subpages.
    - The second option is used to disable all comments.
    """

    def wrapper(*args, **kwargs):
        from .task import get_active_exams_at

        if "author" in kwargs:
            author = kwargs.get("author")
            assignment_id = None
        else:
            author = args[0].user
            assignment_id = kwargs.get("assignment_id")

        # Allways allow teacher access
        if is_teacher(author):
            return function(*args, **kwargs)

        active_exams = get_active_exams_at(author, datetime.now(), timedelta(0.5))

        if not active_exams:
            return function(*args, **kwargs)

        if assignment_id is not None:
            # if task is any of ongoing exams allow it
            for exam in active_exams:
                if exam.pk == assignment_id:
                    return function(*args, **kwargs)

            raise HttpException403("Access to this task is prohibited during exam")
        raise HttpException403("Comments are disabled during exam")

    return wrapper
