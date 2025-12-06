from django.apps import AppConfig
import logging


class CommonConfig(AppConfig):
    name = "common"

    def ready(self):
        # due to how django loads models, we can't import this at the top of the file
        from common.cron_creator import create_crontask

        try:
            # We want to delete containers older than 30 minutes every hour
            create_crontask(
                "deleter",
                "evaluator.old_deleter.delete_old_containers",
                cron_string="0 * * * *",
                args=[("int", "1800")],
            )
        # Database is not running, skip creating the cron task
        except Exception as e:
            logging.warning(f"Could not create task: {e}")
