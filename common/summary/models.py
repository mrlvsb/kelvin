from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict

from common.models import Comment


class IssueCategory(Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Issue:
    file: str
    start_line: int
    end_line: int
    category: IssueCategory
    severity: Severity
    explanation: str


@dataclass
class ReviewResult:
    summary: str
    issues: List[Issue]


@dataclass
class EmbeddedFile:
    path: str
    language: str
    content: str
    linter_comments: Optional[Dict[int, List[Comment]]] = None
    total_lines: int = 0
