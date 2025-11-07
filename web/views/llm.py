from django.core import signing
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


def dump_comment_to_dto(comment: Comment) -> dict:
    return {
        "id": comment.id,
        "author": comment.author.get_full_name(),
        "author_id": comment.author.id,
        "text": comment.text,
        "line": comment.line,
        "source": comment.source,
        "can_edit": True,
        "type": "teacher",
        "unread": True,
    }


@method_decorator(csrf_exempt, name="dispatch")
class ResolveSubmitSuggestion(View):
    def post(self, request, suggestion_id):
        if not is_teacher(request.user):
            raise PermissionDenied()

        suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)

        created_comment = Comment(
            submit=suggestion.submit,
            author=request.user,
            text=suggestion.text,
            source=suggestion.source,
            line=suggestion.line,
        )
        created_comment.save()

        suggestion.state = SuggestionState.ACCEPTED.value
        suggestion.comment = created_comment
        suggestion.save()

        return JsonResponse(dump_comment_to_dto(created_comment))

    def patch(self, request, suggestion_id):
        if not is_teacher(request.user):
            raise PermissionDenied()

        suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)

        body = from_json(dict, request.body)
        modified_text = body.get("modified_text")

        created_comment = Comment(
            submit=suggestion.submit,
            author=request.user,
            text=modified_text if modified_text is not None else suggestion.text,
            source=suggestion.source,
            line=suggestion.line,
        )
        created_comment.save()

        suggestion.state = SuggestionState.ACCEPTED.value
        suggestion.comment = created_comment
        suggestion.save()

        return JsonResponse(dump_comment_to_dto(created_comment))

    def delete(self, request, suggestion_id):
        if not is_teacher(request.user):
            raise PermissionDenied()

        suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)
        suggestion.state = SuggestionState.REJECTED.value
        suggestion.save()

        return JsonResponse({"status": "deleted"})

    def http_method_not_allowed(self, request, *args, **kwargs):
        return JsonResponse({"error": f"Method {request.method} not allowed."}, status=405)


@csrf_exempt
@require_POST
def post_submit_summary_result(request, submit_id):
    if "token" in request.GET:
        token = signing.loads(request.GET["token"], max_age=3600)

        if token.get("submit_id") != submit_id:
            raise PermissionDenied()
    else:
        raise PermissionDenied()

    submit = get_object_or_404(Submit, id=submit_id)

    summary_result: ReviewResult = from_json(ReviewResult, request.body)
    save_submit_review(submit, summary_result)

    return JsonResponse({"status": "success"})
