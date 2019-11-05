from uuid import uuid4
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserToken


@receiver(post_save, sender=User)
def generate_token(sender, instance, created, **kwargs):
    if created:
        token = UserToken()
        token.user = instance
        token.token = uuid4()
        token.save()
