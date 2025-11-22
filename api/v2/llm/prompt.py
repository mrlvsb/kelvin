from ninja import Router
from ninja.errors import HttpError
from serde import to_dict

from api.auth import require_auth_token
from common.models import LlmReviewPrompt

router = Router()


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

    return to_dict(prompt.to_dto())
