from datetime import timedelta

from django.core.management.base import BaseCommand
from common.cron_creator import create_repeatable_task


class Command(BaseCommand):
    """
    Periodically try to send an e-mail from the e-mail queue.
    """

    def handle(self, *args, **opts):
        create_repeatable_task(
            "email-send",
            "common.emails.try_send_email_from_queue",
            queue="default",
            interval=timedelta(seconds=30),
        )
