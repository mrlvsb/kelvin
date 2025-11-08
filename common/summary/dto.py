from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

from serde import serde


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SuggestionState(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"


@serde
@dataclass
class SuggestedSummaryDTO:
    id: int
    text: str
    state: SuggestionState


@serde
@dataclass
class SuggestedCommentDTO:
    id: int
    source: str
    line: int
    text: str
    severity: Severity
    state: SuggestionState


@serde
@dataclass
class ReviewResult:
    summary: SuggestedSummaryDTO
    suggestions: List[SuggestedCommentDTO]


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
    language: str = "english"

    @staticmethod
    def from_dict(submit_config: Dict) -> "LlmConfig":
        async_section = submit_config.get("async", {})
        llm_section = async_section.get("llm", {})

        return LlmConfig(enabled=llm_section.get("enabled", False))
