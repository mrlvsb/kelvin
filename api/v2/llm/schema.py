from datetime import datetime

from ninja import Schema


class ModifySuggestionSchema(Schema):
    modified_text: str | None = None


class RateSuggestionSchema(Schema):
    rating: int


class OpenAIServerSchema(Schema):
    id: str
    label: str
    models: list[str]


class LlmReviewPromptSchema(Schema):
    id: int
    name: str
    description: str
    version: int
    text: str
    created_at: datetime
    default: bool
