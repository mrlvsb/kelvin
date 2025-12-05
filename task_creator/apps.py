from django.apps import AppConfig, apps


class TaskCreatorConfig(AppConfig):
    name = "task_creator"

    def ready(self):
        # due to how django loads models, we can't import this at the top of the file
        from task_creator.cron_creator import create_crontask

        try:
            create_crontask(
                "deleter",
                "evaluator.old_deleter.delete_old_containers",
                "0 * * * *",
                args=[("int", "1800")],
            )
        # Database is not running, skip creating the cron task
        except Exception:
            pass
