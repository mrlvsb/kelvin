from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from common.utils import inbus_search_user

class Command(BaseCommand):
    def handle(self, *args, **opts):
        users = User.objects.filter(Q(email="") | Q(first_name="") | Q(last_name=""))

        for user in users:
            person_inbus = inbus_search_user(user.username)
            if not person_inbus:
                print(f"User {user.username} not found")
                continue

            user.first_name = person_inbus.first_name
            user.last_name = person_inbus.second_name
            user.email = person_inbus.email
            user.save()
