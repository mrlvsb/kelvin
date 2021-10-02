import os
import logging

from . import testsets
from .results import EvaluationResult

from rq import get_current_job

logger = logging.getLogger("evaluator")


class Evaluation:
    def __init__(self, task_path : str, submit_path: str, result_path: str, meta=None):
        self.task_path = task_path
        self.submit_path = submit_path
        self.result_path = result_path
        self.result = None
        self.meta = meta
        self.tests = testsets.TestSet(task_path, meta)
        os.makedirs(result_path)

    def run(self):
        job = get_current_job()
        job.meta['actions'] = len(self.tests.pipeline)
        job.meta['current_action'] = 0
        job.save_meta()

        self.result = EvaluationResult(self.result_path)
        failed = False
        for pipe in self.tests.pipeline:
            if not failed or pipe.enabled == 'always':
                if not pipe.enabled or (self.meta['before_announce'] and not pipe.enabled == 'announce'):
                    logger.info(f"skipping {pipe.id}")
                    continue

                logger.info(f"executing {pipe.id}")
                res = pipe.run(self)
                if res:
                    res['id'] = pipe.id
                    res['title'] = pipe.title
                    self.result.pipelines.append(res)

                    if pipe.fail_on_error and 'failed' in res and res['failed']:
                        failed = True

            job.meta['current_action'] += 1
            job.save_meta()

        self.result.save(os.path.join(self.result_path, 'result.json'))
        return self.result
