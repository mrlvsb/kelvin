import abc
from abc import ABC
from typing import Any, TYPE_CHECKING


if TYPE_CHECKING:
    from ..evaluation import EvaluationContext, EvaluationPaths
    from ..results import EvaluationResult


class Job(ABC):
    @abc.abstractmethod
    def run(
        self, paths: "EvaluationPaths", ctx: "EvaluationContext", result: "EvaluationResult"
    ) -> Any:
        raise NotImplementedError
