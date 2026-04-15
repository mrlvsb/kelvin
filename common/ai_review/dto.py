import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import List

from serde import serde


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewMode(Enum):
    CHAIN_OF_THOUGHT = "chain_of_thought"
    ZERO_SHOT = "zero_shot"
    THINKING = "thinking"


@serde
@dataclass
class EmbeddedFile:
    path: str
    language: str
    content: str
    total_lines: int = 0


class SuggestionState(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"
    DISMISSED = "dismissed"


# ---------------------------------------------------------------------------
# Draft pass
# ---------------------------------------------------------------------------


@serde
@dataclass
class EvidenceItem:
    line: int
    snippet: str
    relevance: str


@serde
@dataclass
class CandidateIssue:
    source: str
    category: str
    severity: str
    line: int
    title: str
    reasoning: str
    evidence: List[EvidenceItem]
    why_it_matters: str
    suggested_fix: str
    confidence: str
    false_positive_risk: str
    critique_note: str = field(default="")


@serde
@dataclass
class DraftObservation:
    source: str
    note: str


@serde
@dataclass
class DraftStatistics:
    sources: int
    total_lines: int
    candidate_issue_count: int


@serde
@dataclass
class DraftResult:
    stats: DraftStatistics
    reasoning_trace: str
    observations: List[DraftObservation]
    candidate_issues: List[CandidateIssue]


# ---------------------------------------------------------------------------
# Review pass
# ---------------------------------------------------------------------------


@serde
@dataclass
class ReviewIssue:
    source: str
    severity: Severity
    explanation: str
    line: int

    def location(self) -> str:
        return f"({self.source}:{self.line})"


@serde
@dataclass
class AIReviewRequest:
    review_mode: ReviewMode
    prompt_name: str
    server_id: str
    model: str


@serde
@dataclass
class AIReviewResult:
    summary: str
    issues: List[ReviewIssue]


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


@serde
@dataclass
class SuggestedCommentDTO:
    id: int
    source: str | None
    line: int | None
    text: str
    quality_rating: int | None
    relevance_rating: int | None
    severity: Severity
    state: SuggestionState


@serde
@dataclass
class SubmitReviewResultDTO:
    summary: SuggestedCommentDTO
    suggestions: List[SuggestedCommentDTO]
    review_mode: ReviewMode
    prompt_name: str
    server_id: str
    model: str


@serde
@dataclass
class LlmReviewPromptDTO:
    id: int
    name: str
    description: str
    version: int
    text: str
    created_at: datetime.datetime | None
    default: bool


@serde
@dataclass
class OpenAIServerDTO:
    id: str
    label: str
    base_url: str
    api_key: str
    models: list[str]


@serde
@dataclass
class LlmConfig:
    enabled: bool
    mode: ReviewMode
    language: str | None
    model: str | None
    prompt: str | None
    server: str | None
