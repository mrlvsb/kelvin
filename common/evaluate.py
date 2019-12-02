import django_rq
from evaluator.evaluator import evaluate
from common.models import Submit, submit_path_parts
import json
import os
from django.conf import settings


def get_meta(user):
    return {
        'username': user.username,
    }

@django_rq.job
def evaluate_job(s: Submit):
    result_path = os.path.join(
        'submit_results',
        *submit_path_parts(s),
        f"{s.student.username}_{s.submit_num}"
    )

    result = evaluate(
        "tasks/{}".format(s.assignment.task.code),
        s.source.path,
        result_path,
        get_meta(s.student),
    )

    # calculate points
    s.points = 0
    s.max_points = 0
    for i in result:
        for test in i.tests:
            if test.success:
                s.points += 1
            s.max_points += 1

    s.save()