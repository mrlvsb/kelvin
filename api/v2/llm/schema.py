import re
from datetime import datetime

from ninja import Schema
from pydantic import field_validator


class ModifySuggestionSchema(Schema):
    modified_text: str | None = None


class RateSuggestionSchema(Schema):
    rating: int


class PromptResponse(Schema):
    id: int
    name: str
    description: str
    version: int
    text: str
    created_at: datetime | None
    updated_at: datetime | None
    default: bool
    is_deleted: bool
    author_username: str | None
    author_full_name: str | None
    updated_by_username: str | None
    updated_by_full_name: str | None


class PromptCreateRequest(Schema):
    name: str
    description: str = ""
    text: str

    @field_validator("name")
    @classmethod
    def name_must_be_snake_case(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", v):
            raise ValueError(
                "Prompt name must be snake_case (lowercase letters, digits, and underscores, starting with a letter)."
            )
        return v


class PromptUpdateRequest(Schema):
    text: str | None = None


class PromptDescriptionUpdateRequest(Schema):
    description: str
