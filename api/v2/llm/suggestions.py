from django.shortcuts import get_object_or_404
from django_cas_ng.decorators import user_passes_test
from ninja import Router
from ninja.errors import HttpError
from serde import to_dict

from api.v2.llm.schema import ModifySuggestionSchema, RateSuggestionSchema
from common.ai_review.dto import SuggestionState
from common.comment import comment_to_dto
from common.models import Comment, SuggestedComment
from common.utils import is_teacher

router = Router()


# TODO: Add check, to ensure that only teacher, that teach the course can accept/reject suggestions


@router.post(
    "/{suggestion_id}/rate",
    url_name="rate_submit_suggestion",
    summary="Rate suggested comment",
    description="Rate an AI-suggested comment as helpful or not.",
)
@user_passes_test(is_teacher)
def rate_submit_suggestion(request, suggestion_id: int, body: RateSuggestionSchema):
    suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)

    if not (0 <= body.rating <= 10):
        raise HttpError(400, "Rating must be between 0 and 10")

    suggestion.rating = body.rating
    suggestion.save()

    return {"status": "success"}


@router.post(
    "/{suggestion_id}",
    url_name="accept_submit_suggestion",
    summary="Accept suggested comment",
    description="Accept an AI-suggested comment as a teacher.",
)
@user_passes_test(is_teacher)
def accept_submit_suggestion(request, suggestion_id: int):
    suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)

    if suggestion.state != SuggestionState.PENDING.value:
        raise HttpError(400, "Only pending suggestions can be accepted")

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

    # TODO: Handle notifications

    return to_dict(comment_to_dto(created_comment, can_edit=True, type="teacher", unread=False))


@router.patch(
    "/{suggestion_id}",
    url_name="modify_submit_suggestion",
    summary="Modify and accept suggested comment",
    description="Modify a suggested comment text before accepting it.",
)
@user_passes_test(is_teacher)
def modify_submit_suggestion(request, suggestion_id: int, body: ModifySuggestionSchema):
    suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)

    if suggestion.state != SuggestionState.PENDING.value:
        raise HttpError(400, "Only pending suggestions can be modified and accepted")

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

    # TODO: Handle notifications

    return to_dict(comment_to_dto(created_comment, can_edit=True, type="teacher", unread=False))


@router.delete(
    "/{suggestion_id}",
    url_name="decline_submit_suggestion",
    summary="Reject suggested comment",
    description="Reject an AI-suggested comment as a teacher.",
)
@user_passes_test(is_teacher)
def decline_submit_suggestion(request, suggestion_id: int):
    suggestion = get_object_or_404(SuggestedComment, id=suggestion_id)

    if suggestion.state != SuggestionState.PENDING.value:
        raise HttpError(400, "Only pending suggestions can be rejected")

    suggestion.state = SuggestionState.REJECTED.value
    suggestion.save()

    return {"status": "deleted"}
