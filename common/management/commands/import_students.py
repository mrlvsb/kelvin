import datetime
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from common.models import Class

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('file', help='saved html from edison')

    def handle(self, *args, **opts):
        from lxml.html import parse
        doc = parse(opts['file']).getroot()

        classes = list(map(str.strip, doc.xpath('//tr[@class="rowClass1"]/th/div/span[1]/text()')))
        labels = list(doc.xpath('//tr[@class="rowClass1"]/th/div/@title'))

        class_in_db = {}
        for c, label in zip(classes, labels):
            try:
                class_in_db[c] = Class.objects.get(code=c)
            except Class.DoesNotExist:
                s = label.split(' ')

                class_in_db[c] = Class()
                class_in_db[c].code = c
                class_in_db[c].day = s[6]
                class_in_db[c].hour = s[7]
                class_in_db[c].year = datetime.datetime.now().year
                class_in_db[c].winter = datetime.datetime.now().month >= 9
                class_in_db[c].time = s[7]
                class_in_db[c].save()

        for row in doc.xpath('//table[@class="dataTable"]//tr'):
            if 'class' in row.attrib and 'rowClass1' == row.attrib['class']:
                continue

            login = row.xpath('./td[2]/a/text()')[0].strip()
            email = row.xpath('./td[2]/a/@href')[0].replace('mailto:', '').strip()
            name = row.xpath('./td[3]/a/text()')[0].replace(', Ing.', '').replace(', Bc.', '')
            lastname, firstname = name.strip().split(' ', 1)

            clazz = None
            for i, el in enumerate(row.xpath('.//input')):
                if "checked" in el.attrib:
                    if classes[i][0] != 'P':
                        if clazz is not None:
                            raise "in multiple classess"
                        clazz = classes[i]

            if clazz:
                try:
                    User.objects.get(username=login)
                except User.DoesNotExist:
                    print(f"Creating user {login.upper()}")
                    user = User.objects.create_user(login.upper(), email)
                    user.first_name = firstname
                    user.last_name = lastname
                    user.save()

                    class_in_db[clazz].students.add(user)
            else:
                 print(login, email, firstname, lastname, clazz, " have no class")

