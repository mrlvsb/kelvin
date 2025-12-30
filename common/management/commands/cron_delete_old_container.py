from django.core.management.base import BaseCommand
from common.cron_creator import create_crontask
import logging


class Command(BaseCommand):
    def handle(self, *args, **opts):
        try:
            # We want to delete containers older than 30 minutes every hour
            create_crontask(
                "deleter",
                "evaluator.docker_container_cleanup.delete_old_containers",
                cron_string="0 * * * *",
                args=[("int", "1800")],
                queue="evaluator",
            )
        # Database is not running, skip creating the cron task
        except Exception as e:
            logging.warning(f"Could not create task: {e}")
