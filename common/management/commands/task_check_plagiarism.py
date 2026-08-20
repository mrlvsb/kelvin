from datetime import timedelta

from django.core.management.base import BaseCommand
from common.task_creator import create_repeatable_task


class Command(BaseCommand):
    """
    Periodically run MOSS plagiarism check.
    """

    def handle(self, *args, **opts):
        create_repeatable_task(
            "moss-plagiarism-check",
            "common.plagcheck.moss.periodic_moss_check",
            interval=timedelta(minutes=15),
            queue="default",
        )
