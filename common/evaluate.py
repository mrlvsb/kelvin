import django_rq
from django.urls import reverse
from django.core import signing

from evaluator.evaluator import Evaluation
import os
import io
import requests
import tempfile
import tarfile
import logging


def evaluate_submit(request, submit, meta=None):
    submit_url = request.build_absolute_uri(reverse('task_detail', kwargs={
        'login': submit.student.username,
        'assignment_id': submit.assignment_id,
        'submit_num': submit.submit_num,
    }))
    task_url = request.build_absolute_uri(reverse('teacher_task_tar', kwargs={
        'task_id': submit.assignment.task_id,
    }))
    token = signing.dumps({
        'submit_id': submit.id,
        'task_id': submit.assignment.task_id,
    })
    return django_rq.enqueue(
        evaluate_job,
        submit_url,
        task_url,
        token,
        {
            **get_meta(submit.student.username),
            **(meta if meta else {})
        }
    )


def get_meta(login):
    return {
        'login': login,
    }


@django_rq.job
def evaluate_job(submit_url, task_url, token, meta):
    logging.basicConfig(level=logging.DEBUG)
    s = requests.Session()

    logging.info(f"Evaluating {submit_url}")

    with tempfile.TemporaryDirectory() as workdir:
        os.chdir(workdir)

        def untar(url, dest):
            res = s.get(url)
            if res.status_code != 200:
                raise Exception(f"Failed to download source code: {res.status_code}")
            with tarfile.open(fileobj=io.BytesIO(res.content)) as tar:
                tar.extractall(dest)

        untar(f'{submit_url}download?token={token}', 'submit')
        untar(f'{task_url}?token={token}', 'task')

        base = os.getcwd()

        Evaluation(
            os.path.join(base, 'task'),
            os.path.join(base, 'submit'),
            os.path.join(base, 'result'),
            meta,
        ).run()

        f = io.BytesIO()
        with tarfile.open(fileobj=f, mode='w') as tar:
            tar.add(os.path.join(base, 'result'), '')

        f.seek(0, io.SEEK_SET)
        res = s.put(
            f'{submit_url}result?token={token}',
            data=f, headers={
                'Content-Type': 'application/x-tar',
            }
        )
        if res.status_code != 200:
            raise Exception(f"Failed to upload results: {res.status_code}")
