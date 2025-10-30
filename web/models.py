from dataclasses import dataclass

from serde import serde

from common.models import Submit
from common.summary.models import ReviewResult
from evaluator.results import EvaluationResult


@serde
@dataclass
class SubmitData:
    submit: Submit
    results: EvaluationResult
    summary: ReviewResult
