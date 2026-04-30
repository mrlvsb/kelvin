from django.contrib.auth.decorators import user_passes_test
from ninja import Router
from ninja.errors import HttpError

from api.auth import require_auth_token
from api.v2.llm.schema import LlmReviewPromptSchema
from common.models import LlmReviewPrompt
from common.utils import is_teacher

router = Router()


def map_to_scheme(prompt: LlmReviewPrompt) -> LlmReviewPromptSchema:
    return LlmReviewPromptSchema(
        id=prompt.id,
        name=prompt.name,
        description=prompt.description,
        version=prompt.version,
        text=prompt.text,
        created_at=prompt.created_at,
        default=prompt.default,
    )


@router.get(
    "/{prompt_name}",
    url_name="retrieve_llm_review_prompt",
    summary="Retrieve LLM Review Prompt",
    description="Retrieve the most recent LLM review prompt by name.",
)
@require_auth_token
def retrieve_llm_review_prompt(request, prompt_name: str):
    prompt = LlmReviewPrompt.objects.filter(name=prompt_name).order_by("version").first()

    if not prompt:
        return HttpError(404, f"LLM Review Prompt with name '{prompt_name}' not found.")

    return map_to_scheme(prompt)


@router.get(
    "/",
    url_name="list_llm_review_prompts",
    summary="List LLM Review Prompts",
    description="List all LLM review prompts with their latest versions.",
)
@user_passes_test(is_teacher)
def list_llm_review_prompts(request):
    prompts = LlmReviewPrompt.objects.order_by("name", "-version").distinct("name")

    return [map_to_scheme(prompt) for prompt in prompts]
