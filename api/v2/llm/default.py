from django.contrib.auth.decorators import user_passes_test
from ninja import Router

from api.v2.llm.schema import OpenAIServerSchema
from common.ai_review.openai_config import get_openai_servers
from common.utils import is_teacher

router = Router()


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
