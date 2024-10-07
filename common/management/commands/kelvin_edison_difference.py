from django.core.management.base import BaseCommand

from django.core.cache import cache

from common.models import Class, Subject
from common.inbus import inbus
from common.inbus.dto import SubjectVersionId


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("subject")

    def handle(self, *args, **opts):
        subject = Subject.objects.get(abbr__icontains=opts["subject"])
        subject_versions = cache.get("subject_versions")

        if not subject_versions:
            subject_versions = inbus.subject_versions()
            cache.set("subject_versions", subject_versions, 60 * 60)
        subject_versions = [
            subject_version
            for subject_version in subject_versions
            if subject_version.subject.abbrev == subject.abbr
        ]
        for subject_version in subject_versions:
            subject_version_schedule = inbus.schedule_subject_by_version_id(
                SubjectVersionId(subject_version.subjectVersionId)
            )

            # mapping of student -> class
            mapping = {}
            for ca in subject_version_schedule:
                students_inbus = [
                    sr.login.upper()
                    for sr in inbus.students_in_concrete_activity(ca.concreteActivityId)
                ]
                code = ca.code()
                if code.startswith("C"):
                    for s in students_inbus:
                        mapping[s] = ca

            for ca in subject_version_schedule:
                students_inbus = [
                    sr.login.upper()
                    for sr in inbus.students_in_concrete_activity(ca.concreteActivityId)
                ]
                code = ca.code()
                if code.startswith("C"):
                    try:
                        print(f"{ca.code()} by {ca.teacherLogins}")
                        clazz = Class.objects.get(code=code, semester__active=True)

                        students_class = [u.username.upper() for u in clazz.students.all()]

                        for k in sorted(students_class):
                            if k not in students_inbus:
                                print(f"\tIN K {k}")
                                other_ca = mapping.get(k)
                                if other_ca:
                                    print(
                                        f"\t\tShould be in {other_ca.code()} by {other_ca.teacherLogins}"
                                    )
                        for i in sorted(students_inbus):
                            if i not in students_class:
                                print(f"\tIN E {i}")

                    except Class.DoesNotExist:
                        print(f"There's a missing class with code: {code}")
