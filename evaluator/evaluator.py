import os
import logging

from . import evaluation
from .results import EvaluationResult

from rq import get_current_job

logger = logging.getLogger("evaluator")


class Evaluation:
    def __init__(self, task_path: str, submit_path: str, result_path: str, meta=None):
        self.task_path = task_path
        self.submit_path = submit_path
        self.result_path = result_path
        self.result = None
        self.meta = meta
        self.tests = evaluation.EvaluationContext(task_path, meta)
        os.makedirs(result_path)

    def run(self):
        rq_job = get_current_job()
        rq_job.meta["actions"] = len(self.tests.pipeline)
        rq_job.meta["current_action"] = 0
        rq_job.save_meta()

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

            rq_job.meta["current_action"] += 1
            rq_job.save_meta()

        self.result.save(os.path.join(self.result_path, "result.json"))
        return self.result
