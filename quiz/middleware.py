from django.http import HttpResponseRedirect
from django.urls import reverse, resolve, Resolver404
from enum import Enum
from kelvin.settings import DEBUG
from quiz.quiz_utils import quiz_running_for_user
if DEBUG:
    try:
        from debug_toolbar.toolbar import DebugToolbar
    except ImportError:
        pass


class SubmitType(Enum):
    PERIODIC = 0
    MANUAL = 1


class QuizRedirectMiddleware:
    """
    Middleware to force redirect to quiz filling page if student quiz is active and preventing to access urls that are not
    allowed to visit during filling the quiz.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        enrolled_quiz = quiz_running_for_user(request.user)

        if enrolled_quiz is not None:
            fill_url = reverse("quiz_fill")

            allowed_urls = [
                fill_url,
                reverse("api_quiz_results", args=[enrolled_quiz.id, SubmitType.PERIODIC.value]),
                reverse("api_quiz_results", args=[enrolled_quiz.id, SubmitType.MANUAL.value]),
                reverse("api_info"),
                reverse("notification_all"),
                reverse("notification_mark_as_read_all"),
                reverse("cas_ng_logout"),
            ]

            try:
                resolved_path = resolve(request.path_info).url_name
                if resolved_path == "quiz_asset":
                    allowed_urls.append(request.path_info)
                elif resolved_path == "notification_mark_as_read_single":
                    allowed_urls.append(request.path_info)
            except Resolver404:
                pass

            debug_toolbar = DEBUG and DebugToolbar.is_toolbar_request(request)
            if not debug_toolbar and request.path_info not in allowed_urls:
                return HttpResponseRedirect(fill_url)

        response = self.get_response(request)

        return response
