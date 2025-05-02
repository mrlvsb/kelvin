from django.http import HttpResponseRedirect
from django.urls import reverse, resolve, Resolver404
from enum import Enum
from quiz.models import EnrolledQuiz


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
        try:
            enrolled_quiz = EnrolledQuiz.objects.get(student=request.user.id, submitted=False)

            fill_url = reverse("quiz_fill")

            allowed_urls = [
                fill_url,
                reverse("api_quiz_results", args=[enrolled_quiz.id, SubmitType.PERIODIC.value]),
                reverse("api_quiz_results", args=[enrolled_quiz.id, SubmitType.MANUAL.value]),
                reverse("cas_ng_logout"),
            ]

            try:
                if resolve(request.path_info).url_name == "quiz_asset":
                    allowed_urls.append(request.path_info)
            except Resolver404:
                pass

            if request.path_info not in allowed_urls:
                return HttpResponseRedirect(fill_url)
        except EnrolledQuiz.DoesNotExist:
            pass

        response = self.get_response(request)

        return response
