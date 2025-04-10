from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest
from django.shortcuts import render
from django.utils.crypto import get_random_string
from django.conf import settings
from django.urls import reverse
from api.models import UserToken
from common.exceptions import HttpExceptionData

from .student import student_index, ui
from common.utils import is_teacher
from api.backends import hash_token


def render_custom_error_page(request: HttpRequest, exception):
    exception = HttpExceptionData.from_exception(exception)
    ctx = dict(
        status_code=exception.status,
        message=exception.message,
    )
    return render(request, "error_page.html", ctx, status=exception.status)


@login_required()
def index(request):
    if is_teacher(request.user):
        return ui(request)
    return student_index(request)


@login_required()
def index_vue(request):
    if is_teacher(request.user):
        return ui_vue(request)
    return student_index(request)


@login_required
def ui_vue(request):
    return render(request, "web/ui_vue.html")


@user_passes_test(is_teacher)
def import_inbus(request):
    return render(request, "web/inbusimport.html", {})


@login_required()
def api_token(request):
    data = {
        "base_url": f"{request.scheme}://{request.META.get('HTTP_HOST', 'localhost:8000')}",
        "doc_token": "YOUR_TOKEN",
    }
    if request.method == "POST":
        token_plaintext = get_random_string(32)
        token_secure = hash_token(token_plaintext)

        try:
            token = UserToken.objects.get(user__id=request.user.id)
            token.token = token_secure
            token.save()
        except UserToken.DoesNotExist:
            token = UserToken()
            token.user = request.user
            token.token = token_secure
            token.save()

        data["token_plaintext"] = token_plaintext
        data["doc_token"] = token_plaintext

    return render(request, "web/common/api_token.html", data)


def template_context(request):
    return {
        "is_teacher": is_teacher(request.user),
        "vapid_public_key": getattr(settings, "WEBPUSH_SETTINGS", {}).get("VAPID_PUBLIC_KEY", ""),
        "webpush_save_url": reverse("save_webpush_info"),
        "sentry_url": settings.SENTRY_URL,
    }
