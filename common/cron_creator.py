from scheduler.models.scheduled_task import CronTask, BaseTask
from scheduler.models.args import TaskArg
from django.contrib.contenttypes.models import ContentType
from typing import List, Tuple


def create_crontask(
    name: str,
    callable,
    cron_string: str,
    args: List[Tuple[str, str]] | None = None,
    enabled=True,
    queue="evaluator",
):
    """Create a CronTask with the given parameters. If a task with the same name exists, it will be deleted first.

    Keyword arguments:
    name -- The name of the cron task.
    callable -- The callable to be executed by the cron task.
    cron_string -- The cron schedule string.
    args -- A list of tuples representing the arguments for the task.
    enabled -- Whether the cron task is enabled.
    queue -- The queue in which the task will be executed.
    """
    existing_job = CronTask.objects.filter(name=name).first()
    if existing_job:
        existing_job.delete()
    deleter_job = CronTask.objects.create(
        name=name,
        callable=callable,
        enabled=enabled,
        queue=queue,
        cron_string=cron_string,
    )
    content_type = ContentType.objects.get_for_model(CronTask)
    for arg in args or []:
        TaskArg.objects.create(
            object_id=deleter_job.id,
            content_type=content_type,
            arg_type=arg[0],
            val=arg[1],
        )
