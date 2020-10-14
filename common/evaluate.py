import django_rq
from evaluator.evaluator import evaluate
from common.models import Submit
import os


def get_meta(login):
    return {
        'login': login,
    }


@django_rq.job
def evaluate_job(s: Submit):
    result_path = os.path.join(
        'submit_results',
        *s.path_parts(),
    )

    evaluate(
        "tasks/{}".format(s.assignment.task.code),
        s.dir(),
        result_path,
        {**get_meta(s.student.username), 'submit_id': s.id},
    )
