import datetime
import re
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from common.models import Class, Semester, Subject
from lxml.html import parse

class ImportException(Exception):
    pass

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('file', help='saved html from edison')
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

    def parse_subject(self, doc):
        h2 = doc.xpath('//h2[@class="nomargin"]')
        if not h2:
            raise ImportException("Missing h2 element")
        subject = re.search(r'\(([^)]+)', h2[0].text)
        if not subject:
            raise ImportException("Subject missing in h2 element")
        return subject.group(1).strip()

    def parse_semester(self, doc):
        elems = doc.xpath('//h2[@class="nomargin"]/span[@class="outputText"]')
        if len(elems) != 2:
            raise ImportException("two elements .outputText with semester not found in h2")
        
        year = elems[0].text.split('/')[0]

        h = elems[1].text.strip().lower()
        if h == 'letní':
            return year, False
        elif h == 'zimní':
            return year, True
        raise ImportException("failed to parse semester")

    def handle(self, *args, **opts):
        doc = parse(opts['file']).getroot()
        subject = Subject.objects.get(abbr=self.parse_subject(doc))

        year, is_winter = self.parse_semester(doc)
        semester = Semester.objects.get(year=year, winter=is_winter)

        classes = list(map(str.strip, doc.xpath('//tr[@class="rowClass1"]/th/div/span[1]/text()')))
        labels = list(doc.xpath('//tr[@class="rowClass1"]/th/div/@title'))

        default_classes = []
        for code in opts['class_code']:
            try:
                default_classes.append(Class.objects.get(semester__year=year, semester__winter=is_winter, code=code, subject__abbr=opts['subject']))
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
                class_in_db[c].day = s[6].upper()
                class_in_db[c].hour = s[7]
                class_in_db[c].year = datetime.datetime.now().year
                class_in_db[c].winter = datetime.datetime.now().month >= 9
                class_in_db[c].time = s[7]
                class_in_db[c].subject = subject
                class_in_db[c].semester = semester

                first_name, last_name = label.replace(',', '').replace('Ph.D.', '').replace('Bc', '').replace('DiS', '').strip().split(' ')[-2:]
                if first_name and last_name:
                    teacher = User.objects.filter(first_name=first_name, last_name=last_name)
                    if not teacher:
                        print(f"Teacher '{first_name}' '{last_name}' not found")
                        exit(1)
                    class_in_db[c].teacher = teacher[0]

                class_in_db[c].save()

        for row in doc.xpath('//table[@class="dataTable"]//tr')[1:]:
            def clean_name(s):
                for remove in ['Ing', 'Bc', 'BA', 'MBA', 'Mgr', 'MgrA', '.', ',']:
                    s = s.replace(remove, '')

                return ' '.join(s.split()).strip()


            login = row.xpath('./td[2]/a/text()')[0].strip()
            email = row.xpath('./td[2]/a/@href')[0].replace('mailto:', '').strip()
            name = clean_name(row.xpath('./td[3]/a/text()')[0])
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
                clazz = classes[i]
                if "checked" in el.attrib:
                    if not self.is_allowed(clazz, opts):
                        continue

                    if user not in class_in_db[clazz].students.all():
                        member_of.append(clazz)
                        class_in_db[clazz].students.add(user)
                elif clazz in class_in_db:
                    class_in_db[clazz].students.remove(user)


            for clazz in default_classes:
                if user not in clazz.students.all():
                    member_of.append(clazz.code)
                    clazz.students.add(user)

            classess = []
            for c in Class.objects.filter(students__username=login, semester__year=year, semester__winter=is_winter):
                classess.append(f"{c.timeslot} {c.teacher.username}")
            print(f"{login} {firstname:>15} {lastname:>15} {('created' if created else ''):>5} {', '.join(classess)}")

