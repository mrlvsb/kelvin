from dataclasses import dataclass
from typing import Optional

from serde import serde

from common.ai_review.dto import AIReviewResult
from common.models import Submit
from evaluator.results import EvaluationResult


@serde
@dataclass
class SubmitData:
    submit: Submit
    results: EvaluationResult
    ai_review: Optional[AIReviewResult]


@dataclass
class PlagiarismEntry:
    link: str
    lines: int
    student_percent: int
    other_percent: int
    other_login: str
