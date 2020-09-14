from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from common.utils import ldap_search_user

class Command(BaseCommand):
    def handle(self, *args, **opts):
        users = User.objects.filter(Q(email="") | Q(first_name="") | Q(last_name=""))

        for user in users:
            info = ldap_search_user(user.username)
            if not info:
                print(f"User {user.username} not found")
                continue

            user.first_name = info['first_name']
            user.last_name = info['last_name']
            user.email = info['email']
            user.save()
