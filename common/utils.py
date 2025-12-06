import io
import os
import re
import tarfile
from datetime import timedelta
from functools import lru_cache
from typing import NewType

import django.contrib.auth.models
import requests
from django.http import HttpRequest
from ipware import get_client_ip

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
    response = session.get(source_url)

    if response.status_code != 200:
        raise Exception(f"Failed to download source code: {response.status_code}")

    with tarfile.open(fileobj=io.BytesIO(response.content)) as tar:
        tar.extractall(destination_path)


def build_absolute_uri(request, location):
    base_uri = os.getenv("API_INTERNAL_BASEURL", None)
    if base_uri:
        return "".join([base_uri, location])
    return request.build_absolute_uri(location)
