import datetime
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from common.models import Class, Semester, Subject
from lxml.html import parse


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('file', help='saved html from edison')
        parser.add_argument('subject', help='subject abbreviation')
        parser.add_argument('semester', help='semester in format YYYY/{W,S}')
        parser.add_argument('--no-lectures', action='store_true', help='do not add students to lectures')
        parser.add_argument('--no-exercises', action='store_true', help='do not add students to exercises')
        parser.add_argument('--class-code', help='add all students to classes with this code', action='append', default=[])

    def is_allowed(self, clazz, opts):
        t, _ = clazz.split('/')

        if t == 'P':
            if opts['no_lectures']:
                return False
        elif t == 'C':
            if opts['no_exercises']:
                return False
        else:
            print(f"Uknown class type: {clazz}")

        return True

    def handle(self, *args, **opts):
        subject = Subject.objects.get(abbr=opts['subject'])

        year = opts['semester'][:-1]
        half = opts['semester'][-1]
        semester = Semester.objects.get(year=year, winter=half=='W')

        doc = parse(opts['file']).getroot()

        classes = list(map(str.strip, doc.xpath('//tr[@class="rowClass1"]/th/div/span[1]/text()')))
        labels = list(doc.xpath('//tr[@class="rowClass1"]/th/div/@title'))

        default_classes = []
        for code in opts['class_code']:
            try:
                default_classes.append(Class.objects.current_semester().get(code=code, subject__abbr=opts['subject']))
            except Class.DoesNotExist:
                print(f"Class with code {code} does not exist.")
                exit(1)

        class_in_db = {}
        for c, label in zip(classes, labels):
            if not self.is_allowed(c, opts):
                continue
            try:
                class_in_db[c] = Class.objects.get(code=c, semester=semester, subject=subject)
            except Class.DoesNotExist:
                s = label.split(' ')

                class_in_db[c] = Class()
                class_in_db[c].code = c
                class_in_db[c].day = s[6]
                class_in_db[c].hour = s[7]
                class_in_db[c].year = datetime.datetime.now().year
                class_in_db[c].winter = datetime.datetime.now().month >= 9
                class_in_db[c].time = s[7]
                class_in_db[c].subject = subject
                class_in_db[c].semester = semester
                class_in_db[c].save()

        for row in doc.xpath('//table[@class="dataTable"]//tr')[1:]:
            login = row.xpath('./td[2]/a/text()')[0].strip()
            email = row.xpath('./td[2]/a/@href')[0].replace('mailto:', '').strip()
            name = row.xpath('./td[3]/a/text()')[0].replace(', Ing.', '').replace(', Bc.', '')
            lastname, firstname = name.strip().split(' ', 1)

            member_of = []
            created = False

            user = None
            try:
                user = User.objects.get(username=login)
            except User.DoesNotExist:
                user = User.objects.create_user(login.upper(), email)
                user.first_name = firstname
                user.last_name = lastname
                user.save()
                created = True

            for i, el in enumerate(row.xpath('.//input')):
                if "checked" in el.attrib:
                        clazz = classes[i]
                        if not self.is_allowed(clazz, opts):
                            continue

                        if user not in class_in_db[clazz].students.all():
                            member_of.append(clazz)
                            class_in_db[clazz].students.add(user)
            for clazz in default_classes:
                if user not in clazz.students.all():
                    member_of.append(clazz.code)
                    clazz.students.add(user)

            print(f"{login} {firstname:>15} {lastname:>15} {('created' if created else ''):>5} {', '.join(member_of)}")

