import csv
import datetime
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from common.models import Class

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('file', help='CSV file with list of students from edison')

    def handle(self, *args, **opts):
        with open(opts['file'], newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                User.objects.update_or_create(
                    username=row['username'],
                    defaults=row
                )
                self.stdout.write(self.style.SUCCESS(f"Creating: {row}"))
