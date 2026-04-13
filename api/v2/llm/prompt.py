from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import Max, Subquery, OuterRef
from ninja import Router
from ninja.errors import HttpError
from serde import to_dict

from api.auth import require_auth_token
from common.models import LlmReviewPrompt
from common.utils import is_teacher
from .schema import (
    PromptResponse,
    PromptCreateRequest,
    PromptUpdateRequest,
    PromptDescriptionUpdateRequest,
)

router = Router()


def prompt_to_response(prompt: LlmReviewPrompt) -> PromptResponse:
    return PromptResponse(
        id=prompt.id,
        name=prompt.name,
        description=prompt.description or "",
        version=prompt.version,
        text=prompt.text,
        created_at=prompt.created_at,
        updated_at=prompt.created_at,
        default=prompt.default,
        is_deleted=prompt.is_deleted,
        author_username=prompt.author.username if prompt.author else None,
        author_full_name=prompt.author.get_full_name() if prompt.author else None,
        updated_by_username=prompt.updated_by.username if prompt.updated_by else None,
        updated_by_full_name=prompt.updated_by.get_full_name() if prompt.updated_by else None,
    )


def check_prompt_permission(user, prompt: LlmReviewPrompt) -> None:
    """Superuser can always modify; teacher only their own prompts."""
    if user.is_superuser:
        return

    if prompt.author_id != user.id:
        raise HttpError(403, "You do not have permission to modify this prompt.")


def get_latest_prompt(prompt_name: str) -> LlmReviewPrompt:
    """Get the latest version of a prompt by name (case-insensitive)."""
    prompt = (
        LlmReviewPrompt.objects.filter(name__iexact=prompt_name)
        .select_related("author", "updated_by")
        .order_by("-version")
        .first()
    )

    if not prompt:
        raise HttpError(404, "Prompt not found.")

    return prompt


@router.get(
    "/{prompt_name}",
    url_name="retrieve_llm_review_prompt",
    description="Retrieve the most recent LLM review prompt by name.",
)
@require_auth_token
def retrieve_llm_review_prompt(request, prompt_name: str):
    prompt = LlmReviewPrompt.objects.filter(name__iexact=prompt_name).order_by("version").first()

    if not prompt:
        return HttpError(404, f"LLM Review Prompt with name '{prompt_name}' not found.")

    return to_dict(prompt.to_dto())


@router.get(
    "/",
    description="List latest version of each prompt. show_deleted includes own deleted prompts (superusers see all deleted).",
)
@user_passes_test(is_teacher)
def list_prompts(request, show_deleted: bool = False):
    from django.db.models import Q

    latest_version = (
        LlmReviewPrompt.objects.filter(name=OuterRef("name")).order_by("-version").values("id")[:1]
    )

    prompts = LlmReviewPrompt.objects.filter(id__in=Subquery(latest_version))

    if show_deleted:
        if request.user.is_superuser:
            pass  # show everything
        else:
            # show non-deleted + own deleted
            prompts = prompts.filter(Q(is_deleted=False) | Q(author=request.user))
    else:
        prompts = prompts.filter(is_deleted=False)

    prompts = prompts.select_related("author", "updated_by").order_by("name")
    return [prompt_to_response(p) for p in prompts]


@router.get(
    "/name/{prompt_name}/versions",
    description="Get all versions of a prompt by name.",
)
@user_passes_test(is_teacher)
def get_prompt_versions(request, prompt_name: str):
    prompts = (
        LlmReviewPrompt.objects.filter(name__iexact=prompt_name)
        .select_related("author", "updated_by")
        .order_by("-version")
    )

    return [prompt_to_response(p) for p in prompts]


@router.post(
    "/",
    description="Create a new prompt (version 1).",
)
@user_passes_test(is_teacher)
def create_prompt(request, payload: PromptCreateRequest):
    existing = LlmReviewPrompt.objects.filter(name__iexact=payload.name).exists()
    if existing:
        raise HttpError(400, f"A prompt with name '{payload.name}' already exists.")

    prompt = LlmReviewPrompt.objects.create(
        name=payload.name,
        description=payload.description,
        text=payload.text,
        version=1,
        author=request.user,
        updated_by=request.user,
    )

    prompt = LlmReviewPrompt.objects.select_related("author", "updated_by").get(id=prompt.id)
    return prompt_to_response(prompt)


@router.put(
    "/{prompt_name}",
    description="Update a prompt's text by creating a new version. Name is immutable.",
)
@user_passes_test(is_teacher)
@transaction.atomic
def update_prompt(request, prompt_name: str, payload: PromptUpdateRequest):
    prompt = get_latest_prompt(prompt_name)
    check_prompt_permission(request.user, prompt)

    latest_version = (
        LlmReviewPrompt.objects.filter(name=prompt.name).aggregate(max_version=Max("version"))[
            "max_version"
        ]
        or 0
    )

    new_prompt = LlmReviewPrompt.objects.create(
        name=prompt.name,
        description=prompt.description,
        text=payload.text if payload.text is not None else prompt.text,
        default=prompt.default,
        version=latest_version + 1,
        author=prompt.author,
        updated_by=request.user,
        is_deleted=prompt.is_deleted,
    )

    new_prompt = LlmReviewPrompt.objects.select_related("author", "updated_by").get(
        id=new_prompt.id
    )
    return prompt_to_response(new_prompt)


@router.patch(
    "/{prompt_name}",
    description="Update the description of the latest prompt version without creating a new version.",
)
@user_passes_test(is_teacher)
def update_prompt_description(request, prompt_name: str, payload: PromptDescriptionUpdateRequest):
    prompt = get_latest_prompt(prompt_name)
    check_prompt_permission(request.user, prompt)

    LlmReviewPrompt.objects.filter(id=prompt.id).update(description=payload.description)
    prompt.refresh_from_db()
    return prompt_to_response(prompt)


@router.delete(
    "/{prompt_name}",
    description="Mark a prompt as deleted (soft delete). All versions are marked. Targets by name.",
)
@user_passes_test(is_teacher)
def delete_prompt(request, prompt_name: str):
    prompt = get_latest_prompt(prompt_name)
    check_prompt_permission(request.user, prompt)

    if prompt.default:
        raise HttpError(
            400, "Cannot delete the default prompt. Set another prompt as default first."
        )

    LlmReviewPrompt.objects.filter(name=prompt.name).update(is_deleted=True)
    return {"status": "deleted"}


@router.patch(
    "/{prompt_name}/restore",
    description="Restore a soft-deleted prompt. Teachers can restore their own; superusers can restore any.",
)
@user_passes_test(is_teacher)
def restore_prompt(request, prompt_name: str):
    prompt = get_latest_prompt(prompt_name)
    check_prompt_permission(request.user, prompt)

    LlmReviewPrompt.objects.filter(name=prompt.name).update(is_deleted=False)
    return {"status": "restored"}


@router.patch(
    "/{prompt_name}/toggle-default",
    description="Set a prompt as the default. Only superusers can do this. Targets by name.",
)
@user_passes_test(is_teacher)
@transaction.atomic
def toggle_default(request, prompt_name: str):
    if not request.user.is_superuser:
        raise HttpError(403, "Only superadmins can set the default prompt.")

    prompt = get_latest_prompt(prompt_name)

    if prompt.default:
        raise HttpError(
            400, "Cannot unset the default prompt. Set another prompt as default first."
        )

    LlmReviewPrompt.objects.all().update(default=False)
    LlmReviewPrompt.objects.filter(name=prompt.name).update(default=True)

    prompt.refresh_from_db()
    return prompt_to_response(prompt)
