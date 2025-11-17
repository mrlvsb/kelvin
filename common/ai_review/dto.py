import datetime
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

from ninja import Schema
from serde import serde

import kelvin.settings


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SuggestionState(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"
    DISMISSED = "dismissed"


@serde
@dataclass
class SubmitSummary:
    id: int
    text: str
    rating: int | None
    model: str
    prompt_id: int
    state: SuggestionState


@serde
@dataclass
class SuggestedCommentDTO:
    id: int
    source: str
    line: int
    text: str
    rating: int | None
    model: str
    prompt_id: int
    severity: Severity
    state: SuggestionState


class LlmReviewPromptDTO(Schema):
    id: int
    name: str
    description: str
    version: int
    text: str
    created_at: datetime.datetime | None
    default: bool


@serde
@dataclass
class AIReviewResult:
    summary: SubmitSummary
    suggestions: List[SuggestedCommentDTO]
    prompt_id: int
    model: str


@serde
@dataclass
class EmbeddedFile:
    path: str
    language: str
    content: str
    total_lines: int = 0


@serde
@dataclass
class LlmConfig:
    enabled: bool
    language: str
    model: str
    prompt_name: str | None

    @staticmethod
    def from_dict(submit_config: Dict) -> "LlmConfig":
        async_section = submit_config.get("async", {})
        llm_section = async_section.get("llm", {})

        return LlmConfig(
            enabled=llm_section.get("enabled", False),
            language=llm_section.get("language", "en"),
            model=llm_section.get("model", kelvin.settings.OPENAI_MODEL),
            prompt_name=llm_section.get("prompt_name", None),
        )
