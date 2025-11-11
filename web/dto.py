from dataclasses import dataclass

from serde import serde

from common.models import Submit
from common.ai_summary.dto import AIReviewResult
from evaluator.results import EvaluationResult


@serde
@dataclass
class SubmitData:
    submit: Submit
    results: EvaluationResult
    ai_review: AIReviewResult


@dataclass
class PlagiarismEntry:
    link: str
    lines: int
    student_percent: int
    other_percent: int
    other_login: str
