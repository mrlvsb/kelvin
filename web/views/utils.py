from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from unidecode import unidecode

from common.models import Submit


def file_response(file, filename: str, mimetype: str) -> HttpResponse:
    response = HttpResponse(file, mimetype)
    response["Content-Disposition"] = f'attachment; filename="{unidecode(filename)}"'
    return response


def authenticate_submit_token_request(request, submit: Submit) -> None:
    if "token" in request.GET:
        token = signing.loads(request.GET["token"], max_age=3600)
        if token.get("submit_id") == submit.id:
            return None

    raise PermissionDenied()
