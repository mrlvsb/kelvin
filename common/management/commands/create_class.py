import datetime
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group
from common.models import Class
from common.utils import current_semester
from argparse import RawTextHelpFormatter

class Command(BaseCommand):
    help = """
create class with students from file

example file:
# nazev;den;cas;ucitel
login1
login2
login3
    """

    def create_parser(self, *args, **kwargs):
        parser = super(Command, self).create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument('files', nargs='+')

    def handle(self, *args, **opts):
        for input_file in opts['files']:
            self.create_class(input_file)

    def create_class(self, path):
        self.stdout.write(f"Importing {path}")
        with open(path) as f:
            header = f.readline()
            headers = header[1:].split(';')
            if header[0] != '#' or len(headers) != 4:
                self.stdout.write(self.style.ERROR(f"invalid header: {header.strip()}, import skipped"))
                return

            name, day, time, teacher_login = map(str.strip, headers)
            self.stdout.write(f"name={name} day={day} time={time} teacher={teacher_login}")
            year, winter = current_semester()
 
            teacher, _ = User.objects.get_or_create(username=teacher_login.upper())
            teacher.groups.add(Group.objects.get(name='teachers'))

            clazz, _ = Class.objects.update_or_create(
                    code=name,
                    year=year,
                    winter=winter,
                    day=day,
                    time=time,
                    teacher=teacher
            )

            for student in f:
                login = student.strip().upper()

                try:
                    clazz.students.add(User.objects.get(username=login))
                    self.stdout.write(self.style.SUCCESS(f"Student {login} assigned"))
                except User.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Student {login} does not exist!"))
        self.stdout.write("")
