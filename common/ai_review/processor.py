import logging
from typing import Optional, Dict

import django_rq
from django.urls import reverse

from common.ai_review.dto import (
    LlmConfig,
    SuggestionState,
    SuggestedCommentDTO,
    Severity,
    ReviewMode,
    SubmitReviewResultDTO,
)
from common.ai_review.job import review_job
from common.models import SuggestedComment, Submit
from common.utils import build_evaluation_download_uri

AI_REVIEW_COMMENT_TYPE: str = "ai-review"
AI_REVIEW_COMMENT_AUTHOR: str = "LLM"
AI_REVIEW_DJANGO_RQ_QUEUE: str = "default"


def parse_llm_config(submit_config: Dict) -> LlmConfig:
    async_section = submit_config.get("async", {})
    llm_section = async_section.get("llm", {})

    return LlmConfig(
        enabled=llm_section.get("enabled", False),
        mode=ReviewMode(llm_section.get("review_mode", ReviewMode.CHAIN_OF_THOUGHT)),
        language=llm_section.get("language", None),
        model=llm_section.get("model", None),
        prompt=llm_section.get("prompt", None),
        server=llm_section.get("server", None),
    )


def enqueue_llm_review_job(
    request, submit: Submit, submit_config: Dict, submit_url: str, token: str
) -> Optional[str]:
    llm_config: LlmConfig = parse_llm_config(submit_config)

    # Skip job if LLM review is not enabled
    if not llm_config.enabled:
        return None

    review_upload_url = build_evaluation_download_uri(
        request,
        reverse(
            "v2:upload_submit_llm_review_result",
            kwargs={
                "submit_id": submit.id,
            },
        ),
    )

    review_prompt_url = build_evaluation_download_uri(
        request,
        reverse(
            "v2:retrieve_llm_review_prompt",
            kwargs={"prompt_name": llm_config.prompt or "default"},
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


def to_suggested_comment_dto(comment: SuggestedComment, is_summary: bool) -> SuggestedCommentDTO:
    return SuggestedCommentDTO(
        id=comment.id,
        source=None if is_summary else comment.source,
        line=None if is_summary else comment.line,
        text=comment.text,
        quality_rating=comment.quality_rating,
        relevance_rating=comment.relevance_rating,
        state=SuggestionState(comment.state),
        severity=Severity.MEDIUM if is_summary else Severity(comment.severity),
    )


def get_submit_review_result(submit: Submit) -> Optional[SubmitReviewResultDTO]:
    comments = SuggestedComment.objects.filter(submit=submit)

    if not comments.exists():
        return None

    summary: SuggestedCommentDTO | None = None
    suggestions: list[SuggestedCommentDTO] = []
    model_id: str | None = None
    prompt_id: str | None = None
    server_id: str | None = None
    review_mode: ReviewMode | None = None

    for comment in comments:
        if not comment.line and not comment.source:
            summary = to_suggested_comment_dto(comment, is_summary=True)
            model_id = comment.model
            prompt_id = comment.prompt.name
            server_id = comment.server
            review_mode = ReviewMode(comment.review_mode)
        else:
            suggestions.append(to_suggested_comment_dto(comment, is_summary=False))

    if summary is None:
        logging.warning(
            f"Unable to construct review for submit {submit.id}, that has no overall summary."
        )
        return None

    return SubmitReviewResultDTO(
        summary=summary,
        suggestions=suggestions,
        review_mode=review_mode,
        prompt_name=prompt_id,
        model=model_id,
        server_id=server_id,
    )
