from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import Router
from serde.json import from_json

from api.auth import require_submit_access_by_token
from api.v2.llm.schema import OpenAIServerSchema
from common.ai_review.dto import AIReviewResult, SubmitSummary
from common.ai_review.openai_config import get_openai_servers
from common.models import Submit
from common.models import SuggestedComment
from common.utils import is_teacher

router = Router()


@router.post(
    "/submit/{submit_id}/result",
    url_name="upload_submit_llm_review_result",
    summary="Upload AI review summary result",
    description="Receive and store the AI summary result for a given submit.",
)
@transaction.atomic
@require_submit_access_by_token
def upload_submit_llm_review_result(request, submit_id: int):
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


@router.get(
    "/servers",
    url_name="list_openai_servers",
    summary="List available OpenAI servers",
    description="Returns configured OpenAI servers available for LLM review tasks.",
)
@user_passes_test(is_teacher)
def list_openai_servers(request):
    return [
        OpenAIServerSchema(id=s.id, label=s.label, models=s.models) for s in get_openai_servers()
    ]
