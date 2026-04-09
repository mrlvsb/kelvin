from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import Router
from serde.json import from_json

from api.auth import require_submit_access_by_token
from common.ai_review.dto import SubmitReviewResultDTO, SuggestedCommentDTO, AIReviewRequest
from common.models import Submit, LlmReviewPrompt
from common.models import SuggestedComment

router = Router()


def from_suggested_comment_dto(
    submit: Submit, request: AIReviewRequest, dto: SuggestedCommentDTO
) -> SuggestedComment:
    return SuggestedComment(
        submit=submit,
        source=dto.source,
        line=dto.line,
        text=dto.text,
        severity=dto.severity.value,
        model=request.model,
        prompt_id=request.prompt_name,
        server=request.server_id,
    )


@router.post(
    "/{submit_id}/result",
    url_name="upload_submit_llm_review_result",
    summary="Upload AI review summary result",
    description="Receive and store the AI summary result for a given submit.",
)
@transaction.atomic
@require_submit_access_by_token
def upload_submit_llm_review_result(request, submit_id: int):
    submit = get_object_or_404(Submit, id=submit_id)

    suggestions: list[SuggestedComment] = []
    review: SubmitReviewResultDTO = from_json(SubmitReviewResultDTO, request.body)
    prompt = get_object_or_404(LlmReviewPrompt, name=review.prompt_name)

    request: AIReviewRequest = AIReviewRequest(
        review_mode=review.review_mode,
        server_id=review.server_id,
        prompt_name=str(prompt.id),
        model=review.model,
    )

    # Save summary
    if review.summary is not None and len(review.summary.text) > 0:
        suggestions.append(from_suggested_comment_dto(submit, request, review.summary))

        # Save suggestions
        suggestions.extend(
            [
                from_suggested_comment_dto(submit, request, suggestion)
                for suggestion in review.suggestions
            ]
        )

        SuggestedComment.objects.filter(submit=submit).delete()
        SuggestedComment.objects.bulk_create(suggestions)

    return {"status": "success"}
