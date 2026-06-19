import logging
import os

from .evaluation import EvaluationContext
from .results import EvaluationResult

logger = logging.getLogger("evaluator")


class Evaluator:
    def __init__(
        self, task_path: str, submit_path: str, result_path: str, eval_ctx: EvaluationContext
    ):
        self.task_path = task_path
        self.submit_path = submit_path
        self.result_path = result_path
        self.result = None
        self.tests = eval_ctx

    def iterate_job_execution(self):
        """
        Execute jobs one by one, yielding after every job.
        """
        os.makedirs(self.result_path)

        self.result = EvaluationResult(self.result_path)
        failed = False
        for job in self.tests.pipeline:
            if not failed:
                logger.info(f"executing {job.id}")
                res = job.job.run(self)
                if res:
                    res["id"] = job.id
                    res["title"] = job.title
                    self.result.pipelines.append(res)

                    if job.fail_on_error and "failed" in res and res["failed"]:
                        failed = True
            yield

        self.result.save(os.path.join(self.result_path, "result.json"))
