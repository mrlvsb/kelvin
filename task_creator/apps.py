from django.apps import AppConfig, apps


class TaskCreatorConfig(AppConfig):
    name = "task_creator"

    def ready(self):
        # models must be imported after they are loaded
        from scheduler.models.scheduled_task import CronTask, BaseTask
        from scheduler.models.args import TaskArg
        from django.contrib.contenttypes.models import ContentType
        existing_job = CronTask.objects.filter(name="deleter").first()
        if existing_job:
            existing_job.delete()
        deleter_job = CronTask.objects.create(
            name="deleter",
            callable="evaluator.old_deleter.delete_old_containers",
            enabled=True,
            queue="evaluator",
            cron_string="0 3 * * *",
                )
        content_type = ContentType.objects.get_for_model(model)
        TaskArg.objects.create(
            object_id=deleter_job.id,
            content_type=content_type,
            arg_type="int",
            val="1800",
            )
