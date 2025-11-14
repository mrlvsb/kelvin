from ninja import Router

from common.exceptions.http_exceptions import HttpException404
from common.models import LlmReviewPrompt

router = Router()


def dump_llm_review_prompt(prompt: LlmReviewPrompt) -> dict:
    return {
        "id": prompt.id,
        "name": prompt.name,
        "description": prompt.description,
        "version": prompt.version,
        "text": prompt.text,
        "created_at": prompt.created_at,
        "default": prompt.default,
    }


# TODO: Add some authentication/authorization?
@router.get(
    "/name/{prompt_name}",
    url_name="retrieve_llm_review_prompt",
    summary="Retrieve LLM Review Prompt",
    description="Retrieve the most recent LLM review prompt by name.",
)
def retrieve_llm_review_prompt(request, prompt_name: str):
    prompt = LlmReviewPrompt.objects.filter(name=prompt_name).order_by("version").first()

    if not prompt:
        return HttpException404(f"LLM Review Prompt with name '{prompt_name}' not found.")

    return dump_llm_review_prompt(prompt)


# TODO: Add some authentication/authorization?
@router.get(
    "/default",
    url_name="retrieve_default_llm_review_prompt",
    summary="Retrieve Default LLM Review Prompt",
    description="Retrieve the most recent LLM review prompt by name.",
)
def retrieve_default_llm_review_prompt(request):
    prompt = LlmReviewPrompt.objects.filter(name="default").order_by("version").first()
    if not prompt:
        return HttpException404("Default LLM Review Prompt not found.")

    return dump_llm_review_prompt(prompt)
