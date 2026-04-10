from datetime import datetime

from ninja import Schema


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


class PromptUpdateRequest(Schema):
    name: str | None = None
    description: str | None = None
    text: str | None = None
