import datetime
from datetime import timedelta

from scheduler.models import RepeatableTask
from scheduler.models.scheduled_task import CronTask
from scheduler.models.args import TaskArg
from django.contrib.contenttypes.models import ContentType
from typing import List, Tuple


def create_crontask(
    name: str,
    callable: str,
    cron_string: str,
    queue: str,
    args: List[Tuple[str, str]] | None = None,
    enabled=True,
):
    """Create a CronTask with the given parameters. If a task with the same name exists, it will be deleted first.

    Keyword arguments:
    name -- The name of the cron task.
    callable -- The callable to be executed by the cron task.
    cron_string -- The cron schedule string.
    queue -- The queue in which the task will be executed.
    args -- A list of tuples representing the arguments for the task.
    enabled -- Whether the cron task is enabled.
    """
    existing_job = CronTask.objects.filter(name=name).first()
    if existing_job:
        existing_job.delete()
    job = CronTask.objects.create(
        name=name,
        callable=callable,
        enabled=enabled,
        queue=queue,
        cron_string=cron_string,
    )
    content_type = ContentType.objects.get_for_model(CronTask)
    for arg in args or []:
        TaskArg.objects.create(
            object_id=job.id,
            content_type=content_type,
            arg_type=arg[0],
            val=arg[1],
        )


def create_repeatable_task(
    name: str,
    callable: str,
    interval: timedelta,
    queue: str,
):
    """Create a RepeatableTask (from django-tasks-scheduler) with the given `interval`.
    If a task with the same name exists, it will be deleted first.
    """
    existing_job = RepeatableTask.objects.filter(name=name).first()
    if existing_job:
        existing_job.delete()
    RepeatableTask.objects.create(
        name=name,
        callable=callable,
        enabled=True,
        queue=queue,
        interval=int(interval.total_seconds()),
        interval_unit=RepeatableTask.TimeUnits.SECONDS,
        scheduled_time=datetime.datetime.now(datetime.UTC),
        # Run forever
        repeat=None,
    )
