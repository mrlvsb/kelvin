from django.shortcuts import get_object_or_404
from django_cas_ng.decorators import user_passes_test
from ninja import Router
from ninja.errors import HttpError

from api.v2.llm.schema import ModifySuggestionSchema
from common.ai_review.dto import SuggestionState
from common.models import Comment, SuggestedComment
from common.utils import is_teacher

router = Router()


# TODO: Move this to shared location and result in CommentDTO
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


@router.post(
    "/rate/{suggestion_id}",
    url_name="rate_submit_suggestion",
    summary="Rate suggested comment",
    description="Rate an AI-suggested comment as helpful or not.",
)
@user_passes_test(is_teacher)
def rate_submit_suggestion(request, suggestion_id: int, query: dict):
    suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)

    rating = query.get("rating")
    if rating is None or not (0 <= rating <= 10):
        raise HttpError(400, "Rating must be between 0 and 10")

    suggestion.rating = rating
    suggestion.save()

    return {"status": "success"}


@router.post(
    "/resolve/{suggestion_id}",
    url_name="accept_submit_suggestion",
    summary="Accept suggested comment",
    description="Accept an AI-suggested comment as a teacher.",
)
@user_passes_test(is_teacher)
def accept_submit_suggestion(request, suggestion_id: int):
    suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)

    created_comment = Comment.objects.create(
        submit=suggestion.submit,
        author=request.user,
        text=suggestion.text,
        source=suggestion.source,
        line=suggestion.line,
    )

    suggestion.state = SuggestionState.ACCEPTED.value
    suggestion.comment = created_comment
    suggestion.save()

    return dump_comment_to_dto(created_comment)


@router.patch(
    "/resolve/{suggestion_id}",
    url_name="modify_submit_suggestion",
    summary="Modify and accept suggested comment",
    description="Modify a suggested comment text before accepting it.",
)
@user_passes_test(is_teacher)
def modify_submit_suggestion(request, suggestion_id: int, body: ModifySuggestionSchema):
    suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)

    created_comment = Comment.objects.create(
        submit=suggestion.submit,
        author=request.user,
        text=body.modified_text if body.modified_text is not None else suggestion.text,
        source=suggestion.source,
        line=suggestion.line,
    )

    suggestion.state = SuggestionState.ACCEPTED.value
    suggestion.comment = created_comment
    suggestion.save()

    return dump_comment_to_dto(created_comment)


@router.delete(
    "/resolve/{suggestion_id}",
    url_name="decline_submit_suggestion",
    summary="Reject suggested comment",
    description="Reject an AI-suggested comment as a teacher.",
)
@user_passes_test(is_teacher)
def decline_submit_suggestion(request, suggestion_id: int):
    suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)
    suggestion.state = SuggestionState.REJECTED.value
    suggestion.save()

    return {"status": "deleted"}


@router.delete(
    "/dismiss/{suggestion_id}",
    url_name="dismiss_submit_suggestion",
    summary="Dismiss suggested comment",
    description="Mark an AI-suggested comment as dismissed. Works for summary.",
)
@user_passes_test(is_teacher)
def dismiss_submit_suggestion(request, suggestion_id: int):
    suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)
    suggestion.state = SuggestionState.DISMISSED.value
    suggestion.save()

    return {"status": "deleted"}
