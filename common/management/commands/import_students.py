from django.core.management.base import BaseCommand
from common.bulk_import import BulkImport

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('file', help='saved html from edison')
        parser.add_argument('--no-lectures', action='store_true', help='do not add students to lectures')
        parser.add_argument('--no-exercises', action='store_true', help='do not add students to exercises')
        parser.add_argument('--class-code', help='add all students to classes with this code', action='append', default=[])

    def handle(self, *args, **opts):
        with open(opts['file']) as f:
            students = BulkImport().run(
                f.read(),
                class_code=opts['class_code'],
                no_lectures=opts['no_lectures'],
                no_exercises=opts['no_exercises'],
            )

            for s in students:
                print(f"{s['login']} {s['firstname']:>15} {s['lastname']:>15} {('created' if s['created'] else ''):>5} {', '.join(s['classes'])}")
