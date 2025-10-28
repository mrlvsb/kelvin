from dataclasses import dataclass
from enum import Enum
from typing import List, Dict


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Issue:
    file: str
    line: int
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
    total_lines: int = 0


@dataclass
class LlmConfig:
    enabled: bool

    @staticmethod
    def from_dict(submit_config: Dict) -> "LlmConfig":
        async_section = submit_config.get("async", {})
        llm_section = async_section.get("llm", {})

        return LlmConfig(enabled=llm_section.get("enabled", False))
