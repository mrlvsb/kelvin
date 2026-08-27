from typing import Any

from common.utils import points_to_color
from . import Job
from ..evaluation import EvaluationContext, EvaluationPaths
from ..results import EvaluationResult


class AutoGraderJob(Job):
    def __init__(
        self, propose: bool = False, after_deadline_multiplier: float = 0.0, overwrite: bool = False
    ):
        self.propose = propose
        self.after_deadline_multiplier = max(0, min(1.0, after_deadline_multiplier))
        self.overwrite = overwrite

    def run(self, paths: EvaluationPaths, ctx: EvaluationContext, result: EvaluationResult) -> Any:
        total = 0
        success = 0
        for action in result.pipelines:
            if "tests" in action:
                total += len(action["tests"])
                success += len(list(filter(lambda t: t["success"], action["tests"])))
            if action.get("failed", False):
                success = 0
                total = 0
                break

        max_points = ctx.meta["max_points"]
        deadline = ctx.meta["deadline"]
        is_after_deadline = deadline and deadline < ctx.meta["submitted_at"]
        points = 0
        if total:
            points = round(
                success
                * max_points
                * (self.after_deadline_multiplier if is_after_deadline else 1)
                / total,
                2,
            )

        result = {
            "html": f"Kelvin {'proposes' if self.propose else 'assigned'} <span style='color: {points_to_color(points, max_points)}'>{points}</span> points from maximal {max_points} points."
        }

        if not self.propose:
            result["points"] = points
            result["points_overwrite"] = self.overwrite
        return result
