import logging
from typing import Optional

import django_rq
from django.urls import reverse

from common.ai_review.dto import (
    LlmConfig,
    AIReviewResult,
    SubmitSummary,
    SuggestionState,
    SuggestedCommentDTO,
    Severity,
)
from common.ai_review.job import review_job
from common.models import SuggestedComment, Submit
from common.utils import build_absolute_uri

AI_REVIEW_COMMENT_TYPE: str = "ai-review"
AI_REVIEW_COMMENT_AUTHOR: str = "LLM"
AI_REVIEW_DJANGO_RQ_QUEUE: str = "default"


def enqueue_llm_review_job(
    request, submit: Submit, submit_config, submit_url: str, token: str
) -> Optional[str]:
    llm_config: LlmConfig = LlmConfig.from_dict(submit_config)

    # Skip job if LLM review is not enabled
    if not llm_config.enabled:
        return None

    review_upload_url = build_absolute_uri(
        request,
        reverse(
            "v2:upload_submit_llm_review_result",
            kwargs={
                "submit_id": submit.id,
            },
        ),
    )

    review_prompt_url = build_absolute_uri(
        request,
        reverse(
            "v2:retrieve_llm_review_prompt",
            kwargs={"prompt_name": llm_config.prompt_name or "default"},
        ),
    )

    summary_queue = django_rq.get_queue(AI_REVIEW_DJANGO_RQ_QUEUE)
    enqueued_job = summary_queue.enqueue(
        review_job,
        submit_url,
        review_upload_url,
        review_prompt_url,
        token,
        llm_config,
        job_timeout=180,
    )

    return enqueued_job.id


def get_submit_review_result(submit: Submit) -> Optional[AIReviewResult]:
    comments = SuggestedComment.objects.filter(submit=submit)

    if not comments.exists():
        return None

    summary: Optional[SubmitSummary] = None
    suggestions: list[SuggestedCommentDTO] = []

    for comment in comments:
        if not comment.line:
            summary = SubmitSummary(
                id=comment.id,
                text=comment.text,
                rating=comment.rating,
                model=comment.model,
                prompt_id=comment.prompt.id,
                state=SuggestionState(comment.state),
            )
        else:
            suggestions.append(
                SuggestedCommentDTO(
                    id=comment.id,
                    source=comment.source,
                    line=comment.line,
                    text=comment.text,
                    rating=comment.rating,
                    model=comment.model,
                    prompt_id=comment.prompt.id,
                    severity=Severity(comment.severity),
                    state=SuggestionState(comment.state),
                )
            )

    if summary is None:
        logging.warning(
            f"Unable to construct review for submit {submit.id}, that has no overall summary."
        )
        return None

    return AIReviewResult(
        summary=summary, suggestions=suggestions, prompt_id=summary.prompt_id, model=summary.model
    )
