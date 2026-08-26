import logging
import os

from .evaluation import EvaluationContext, EvaluationPaths
from .jobs import Job
from .results import EvaluationResult

logger = logging.getLogger("evaluator")


class Evaluator:
    def __init__(self, paths: EvaluationPaths, eval_ctx: EvaluationContext):
        self.paths = paths
        self.result = None
        self.tests = eval_ctx

        # Temporary backcompat
        self.task_path = str(paths.task_dir)
        self.submit_path = str(paths.submit_dir)
        self.result_path = str(paths.result_dir)

    def iterate_job_execution(self):
        """
        Execute jobs one by one, yielding after every job.
        """
        os.makedirs(self.paths.result_dir)

        self.result = EvaluationResult(self.paths.result_dir)
        failed = False
        for job in self.tests.pipeline:
            if not failed:
                logger.info(f"Executing job {type(job.job)} {job.id}")
                if isinstance(job.job, Job):
                    paths = self.paths.with_result_dir(self.paths.result_dir / job.id)
                    res = job.job.run(paths, self.tests)
                else:
                    # Legacy <Foo>Pipe job
                    res = job.job.run(self)
                if res:
                    res["id"] = job.id
                    res["title"] = job.title
                    self.result.pipelines.append(res)

                    if job.fail_on_error and "failed" in res and res["failed"]:
                        failed = True
            yield

        self.result.save(os.path.join(self.paths.result_dir, "result.json"))
