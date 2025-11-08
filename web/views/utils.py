from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect
from unidecode import unidecode

from common.models import Submit
from common.utils import is_teacher


def file_response(file, filename: str, mimetype: str) -> HttpResponse:
    response = HttpResponse(file, mimetype)
    response["Content-Disposition"] = f'attachment; filename="{unidecode(filename)}"'
    return response


def has_permission_for_submit(request, submit: Submit) -> None:
    if "token" in request.GET:
        token = signing.loads(request.GET["token"], max_age=3600)
        if token.get("submit_id") != submit.id:
            raise PermissionDenied()

    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    if not is_teacher(request.user) and request.user.username != submit.student.username:
        raise PermissionDenied()

    return None
