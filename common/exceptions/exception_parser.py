from django.core.exceptions import PermissionDenied, BadRequest
from django.http.response import Http404
from django.conf import settings

from common.exceptions.http_exceptions import (
    HttpException,
    HttpException404,
    HttpException403,
    HttpException400,
)


def parse_exception(request, e):
    # default error pages in DEBUG mode
    if settings.DEBUG:
        return None

    # raise generic errors in api endpoints
    if request.path.startswith("/api/"):
        match e:
            case HttpException400():
                raise BadRequest(e.message)
            case HttpException403():
                raise PermissionDenied(e.message)
            case HttpException404():
                raise Http404(e.message)
            case _:
                return None

    match e:
        case HttpException():
            context = {"status_code": e.code, "title": e.title, "message": str(e)}

        case Http404():
            context = {
                "status_code": 404,
                "title": "Page Not Found",
                "message": "The page you requested does not exist.",
            }
        case PermissionDenied():
            context = {
                "status_code": 403,
                "title": "Forbidden",
                "message": "You are not permitted to view this page.",
            }
        case BadRequest():
            context = {
                "status_code": 400,
                "title": "Bad Request",
                "message": "Sorry, something was off in the request.",
            }
        case _:
            return None  # let django handle unknown exceptions

    context["return_url"] = request.META.get("HTTP_REFERER", "/")  # return to last url or home;
    return context
