from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from serde.json import from_json

from common.models import Submit, SuggestedComment, Comment
from common.summary.dto import ReviewResult, SuggestionState
from common.summary.summary import save_submit_review
from common.utils import is_teacher
from web.views.utils import authenticate_submit_token_request


@method_decorator(csrf_exempt, name="dispatch")
class ResolveSubmitSuggestion(View):
    def post(self, assignment_id, login, submit_num, suggestion_id):
        if not is_teacher(self.request.user):
            raise PermissionDenied()

        submit = get_object_or_404(
            Submit, assignment_id=assignment_id, student__username=login, submit_num=submit_num
        )
        suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)

        suggestion.state = SuggestionState.ACCEPTED
        suggestion.save()

        Comment(
            submit=submit,
            author=self.request.user,
            text=suggestion.text,
            source=suggestion.source,
            line=suggestion.line,
        ).save()

        return JsonResponse({"status": "created"})

    def patch(self, assignment_id, login, submit_num, suggestion_id):
        if not is_teacher(self.request.user):
            raise PermissionDenied()

        submit = get_object_or_404(
            Submit, assignment_id=assignment_id, student__username=login, submit_num=submit_num
        )
        suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)

        suggestion.state = SuggestionState.ACCEPTED
        suggestion.save()

        body = from_json(dict, self.request.body)
        modified_text = body.get("modified_text")

        Comment(
            submit=submit,
            author=self.request.user,
            text=modified_text if modified_text is not None else suggestion.text,
            source=suggestion.source,
            line=suggestion.line,
        ).save()

        return JsonResponse({"status": "updated"})

    def delete(self, _, __, ___, suggestion_id):
        if not is_teacher(self.request.user):
            raise PermissionDenied()

        suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)
        suggestion.state = SuggestionState.REJECTED
        suggestion.save()

        return JsonResponse({"status": "deleted"})

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({"error": f"Method {request.method} not allowed."}, status=405)


@csrf_exempt
@require_POST
def post_submit_summary_result(request, assignment_id, login, submit_num):
    submit = get_object_or_404(
        Submit, assignment_id=assignment_id, student__username=login, submit_num=submit_num
    )

    authenticate_submit_token_request(request, submit)

    summary_result: ReviewResult = from_json(ReviewResult, request.body)
    save_submit_review(submit, summary_result)

    return JsonResponse({"status": "success"})
