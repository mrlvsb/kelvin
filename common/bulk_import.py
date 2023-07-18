import datetime
import re
from common import inbus
from common.utils import user_from_login
import serde
from dataclasses import dataclass
from django.contrib.auth.models import User
from common.models import Class, Semester, Subject
from io import StringIO
from lxml.html import parse
from typing import List, Dict

class ImportException(Exception):
    pass


@serde.serde
@dataclass
class ImportResult:
    login: str
    firstname: str
    lastname: str
    created: bool


class BulkImport:
    def is_allowed(self, clazz, no_lectures, no_exercises):
        t, _ = clazz.split('/')

        if t == 'P':
            if no_lectures:
                return False
        elif t == 'C':
            if no_exercises:
                return False
        else:
            print(f"Uknown class type: {clazz}")

        return True

    def parse_subject(self, doc):
        h2 = doc.xpath('//h2[@class="nomargin"]')
        if not h2:
            raise ImportException("Missing h2 element, have you imported correct file?")
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

    def run(self, content, no_lectures=False, no_exercises=False, class_code=None):
        doc = parse(StringIO(content)).getroot()
        abbr = self.parse_subject(doc)
        try:
            subject = Subject.objects.get(abbr=abbr)
        except Subject.DoesNotExist:
            raise ImportException(f"Subject {abbr} does not exist. Please create it first.")

        year, is_winter = self.parse_semester(doc)
        semester = Semester.objects.get(year=year, winter=is_winter)

        classes = list(map(str.strip, doc.xpath('//tr[@class="rowClass1"]/th/div/span[1]/text()')))
        labels = list(doc.xpath('//tr[@class="rowClass1"]/th/div/@title'))

        default_classes = []
        for code in class_code or []:
            try:
                default_classes.append(Class.objects.get(semester__year=year, semester__winter=is_winter, code=code, subject__abbr=opts['subject']))
            except Class.DoesNotExist:
                raise ImportException(f"Class with code {code} does not exist.")

        class_in_db = {}
        for c, label in zip(classes, labels):
            if not self.is_allowed(c, no_lectures, no_exercises):
                continue
            try:
                class_in_db[c] = Class.objects.get(code=c, semester=semester, subject=subject)
            except Class.DoesNotExist:
                s = label.split(' ')

                class_in_db[c] = Class()
                class_in_db[c].code = c
                day = s[6].upper()
                mapping = {'ÚT': 'UT', 'ČT': 'CT', 'PÁ': 'PA'}
                class_in_db[c].day = mapping.get(day, day)
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
                        raise ImportException(f"Teacher '{first_name}' '{last_name}' not found")
                    class_in_db[c].teacher = teacher[0]

                class_in_db[c].save()

        for row in doc.xpath('//table[@class="dataTable"]//tr')[1:]:
            def clean_name(s):
                for remove in ['Ing', 'Bc', 'BA', 'MBA', 'Mgr', 'MgrA', '.', ',']:
                    s = s.replace(remove, '')

                return ' '.join(s.split()).strip()

            if not row.xpath('./td[2]/a'):
                raise ImportException("Student login not found in table. Have you imported correct file?")

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
                    if not self.is_allowed(clazz, no_lectures, no_exercises):
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
            for c in Class.objects.filter(students__username=login, semester__year=year, semester__winter=is_winter, subject_id=subject.id):
                classess.append(f"{c.timeslot} {c.teacher.username}")

            yield {
                'login': login,
                'firstname': firstname,
                'lastname': lastname,
                'created': created,
                'classes': classess,
            }


    def run_inbus(self, concrete_activities: List[inbus.dto.ConcreteActivity], subj: Dict[str, str], semester: Semester):
        '''
        `subj`: subject from selected subject in UI as dictionary with k:abbr, v: name
        '''

        subject_abbr = subj['abbr']
        try:
            subject = Subject.objects.get(abbr=subject_abbr)
        except Subject.DoesNotExist:
            raise ImportException(f"Subject {subject_abbr} does not exist. Please create it first.")

        # Create classes in DB

        class_in_db = {}
        for ca in concrete_activities:
            c = ca.code()
            try:
                class_in_db[c] = Class.objects.get(code=c, semester=semester, subject=subject)
            except Class.DoesNotExist:
                class_in_db[c] = Class()
                class_in_db[c].code = c
                day = ca.weekDayAbbrev.upper()
                mapping = {'ÚT': 'UT', 'ČT': 'CT', 'PÁ': 'PA'}
                class_in_db[c].day = mapping.get(day, day)
                class_in_db[c].hour = ca.beginTime
                class_in_db[c].year = datetime.datetime.now().year
                class_in_db[c].winter = semester.winter # or ca.semesterTypeId == 1
                class_in_db[c].time = ca.beginTime
                class_in_db[c].subject = subject
                class_in_db[c].semester = semester

                # Teacher
                # TODO: There may be more teachers for a class
                try:
                    teacher = User.objects.get(username=ca.teacherLogins.upper())
                except User.DoesNotExist:
                    teacher = user_from_login(ca.teacherLogins.upper())

                class_in_db[c].teacher = teacher
                class_in_db[c].save()


            # Students
            students_in_class = inbus.inbus.students_in_concrete_activity(ca.concreteActivityId)

            for student in students_in_class:
                login = student.login.upper()
                firstname, lastname = student.firstName, student.secondName

                created = False

                user = None
                try:
                    user = User.objects.get(username=login)
                except User.DoesNotExist:
                    user = user_from_login(login)
                    created = True

                class_in_db[c].students.add(user)

                yield ImportResult(login, firstname, lastname, created)
