from ninja import Router
from ninja.errors import HttpError

from api.auth import require_auth_token
from common.models import LlmReviewPrompt

router = Router()


@router.get(
    "/name/{prompt_name}",
    url_name="retrieve_llm_review_prompt",
    summary="Retrieve LLM Review Prompt",
    description="Retrieve the most recent LLM review prompt by name.",
)
@require_auth_token
def retrieve_llm_review_prompt(request, prompt_name: str):
    prompt = LlmReviewPrompt.objects.filter(name=prompt_name).order_by("version").first()

    if not prompt:
        return HttpError(404, f"LLM Review Prompt with name '{prompt_name}' not found.")

    return prompt.to_dto()


@router.get(
    "/default",
    url_name="retrieve_default_llm_review_prompt",
    summary="Retrieve Default LLM Review Prompt",
    description="Retrieve the most recent LLM review prompt by name.",
)
@require_auth_token
def retrieve_default_llm_review_prompt(request):
    prompt = LlmReviewPrompt.objects.filter(name="default").order_by("version").first()

    if not prompt:
        return HttpError(404, "Default LLM Review Prompt not found.")

    return prompt.to_dto()
