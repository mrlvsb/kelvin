from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.utils.crypto import get_random_string
from django.conf import settings
from django.urls import reverse
from api.models import UserToken

from .student import student_index, ui
from common.utils import is_teacher
from api.backends import hash_token


def custom_403_page(request, exception=None):
    previous_url = request.META.get("HTTP_REFERER", "/")  # return to last url or home
    context = {
        "status_code": 403,
        "title": "Forbidden",
        "message": str(exception) if exception else "You are not permitted to view this page.",
        "return_url": previous_url,
    }
    return render(request, "error_page.html", context)


def custom_400_page(request, exception=None):
    previous_url = request.META.get("HTTP_REFERER", "/")  # return to last url or home
    context = {
        "status_code": 400,
        "title": "Bad Request",
        "message": str(exception) if exception else "Sorry, something was off in the request.",
        "return_url": previous_url,
    }
    return render(request, "error_page.html", context)


def custom_404_page(request, exception=None):
    previous_url = request.META.get("HTTP_REFERER", "/")  # return to last url or home
    context = {
        "status_code": 404,
        "title": "Page Not Found",
        "message": str(exception) if exception else "The page you requested does not exist.",
        "return_url": previous_url,
    }
    return render(request, "error_page.html", context)


@login_required()
def index(request):
    if is_teacher(request.user):
        return ui(request)
    return student_index(request)


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
