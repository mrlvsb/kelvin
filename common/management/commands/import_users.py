import sys

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from common.utils import ldap_search_user

class Command(BaseCommand):
    def handle(self, *args, **opts):
        for line in sys.stdin:
            login = line.rstrip().upper()

            info = ldap_search_user(login)
            if not info:
                print(f"User {login} not found")
                continue

            _, created = User.objects.update_or_create(
                username=login,
                defaults=info
            )
            print(f"{login} {'created' if created else 'updated'}")
