from django.conf import settings
from django.contrib.auth.models import User
from django.db import models


class Email(models.Model):
    """
    E-mail sent by Kelvin.
    """

    class Meta:
        indexes = [
            models.Index(name="sent_at", fields=["sent_at"]),
        ]

    subject = models.TextField()
    text = models.TextField()
    # Do not create backwards FK links, because it clashes with the email attribute of users
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    # If NULL, the e-mail has not been sent yet
    sent_at = models.DateTimeField(null=True, default=None)
    # How many times have we attempted to send this e-mail?
    attempt_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def create(subject: str, text: str, receiver: User) -> "Email":
        email = Email(subject=subject, text=text, receiver=receiver)
        email.save()
        return email
