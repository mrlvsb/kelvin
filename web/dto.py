from dataclasses import dataclass

from serde import serde

from common.models import Submit
from common.summary.dto import ReviewResult
from evaluator.results import EvaluationResult


@serde
@dataclass
class SubmitData:
    submit: Submit
    results: EvaluationResult
    summary: ReviewResult


@dataclass
class PlagiarismEntry:
    link: str
    lines: int
    student_percent: int
    other_percent: int
    other_login: str
