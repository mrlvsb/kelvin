import datetime
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from common.models import Class

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('file', help='CSV file with list of students from edison')
        parser.add_argument('year', help='academic year')

    def handle(self, *args, **opts):
        label = 'Komb ' + opts['year']
        try:
            clazz = Class.objects.get(code=label)
        except Class.DoesNotExist:
            s = label.split(' ')

            clazz = Class()
            clazz.code = label
            clazz.day = 'PaSo'
            clazz.year = datetime.datetime.now().year
            clazz.winter = datetime.datetime.now().month >= 9
            clazz.time = '00:00:00'
            clazz.save()

        try:
            filename = opts['file']
            with open(filename, 'rt') as f:
                for line in f:
                    login, fullname = line.strip().split(';')
                    login = login.strip().upper()

                    fullname = fullname.strip()
                    fullname = fullname.replace(', Ing.', '').replace(', Bc.', '')
                    lastname, firstname = fullname.strip().split(' ', 1)

                    email = login.lower() + '@vsb.cz'

                    try:
                        User.objects.get(username=login)
                    except User.DoesNotExist:
                        user = User.objects.create_user(login.upper(), email)
                        user.first_name = firstname
                        user.last_name = lastname
                        user.save()

                        clazz.students.add(user)
        except FileNotFoundError as e:
            print(e)
