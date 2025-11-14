from django.core import signing
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError
from serde.json import from_json

from common.ai_review.dto import AIReviewResult, SubmitSummary
from common.models import Submit
from common.models import SuggestedComment

router = Router()


@router.post(
    "/submit/{submit_id}/result",
    url_name="upload_submit_llm_review_result",
    summary="Upload AI review summary result",
    description="Receive and store the AI summary result for a given submit.",
)
def upload_submit_llm_review_result(request, submit_id: int, token: str):
    try:
        decoded_token = signing.loads(token, max_age=3600)
    except Exception:
        raise HttpError(403, "Invalid or expired token")

    if decoded_token.get("submit_id") != submit_id:
        raise HttpError(403, "Permission denied")

    submit = get_object_or_404(Submit, id=submit_id)
    review: AIReviewResult = from_json(AIReviewResult, request.body)
    suggestions: list[SuggestedComment] = []

    # Save summary
    if review.summary is not None and len(review.summary.text) > 0:
        summary: SubmitSummary = review.summary

        suggestions.append(
            SuggestedComment(
                submit=submit,
                source=None,
                line=None,
                text=summary.text,
                model=summary.model,
                prompt_id=summary.prompt_id,
            )
        )

    # Save suggestions
    suggestions.extend(
        [
            SuggestedComment(
                submit=submit,
                source=suggestion.source,
                line=suggestion.line,
                text=suggestion.text,
                severity=suggestion.severity.value,
                model=suggestion.model,
                prompt_id=suggestion.prompt_id,
            )
            for suggestion in review.suggestions
        ]
    )

    SuggestedComment.objects.filter(submit=submit).delete()
    SuggestedComment.objects.bulk_create(suggestions)

    return {"status": "success"}
