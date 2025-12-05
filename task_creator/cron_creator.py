from scheduler.models.scheduled_task import CronTask, BaseTask
from scheduler.models.args import TaskArg
from django.contrib.contenttypes.models import ContentType


def create_crontask(name, callable, cron_string, args=[], enabled=True, queue="evaluator"):
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
    for arg in args:
        TaskArg.objects.create(
            object_id=deleter_job.id,
            content_type=content_type,
            arg_type=arg[0],
            val=arg[1],
        )
