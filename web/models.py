from dataclasses import dataclass

from serde import serde

from common.models import Submit
from evaluator.results import EvaluationResult


@serde
@dataclass
class SubmitData:
    submit: Submit
    results: EvaluationResult
