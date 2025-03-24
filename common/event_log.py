import dataclasses
import datetime
import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import JSONField
from django.http import HttpRequest

if TYPE_CHECKING:
    from .models import AssignedTask
from .utils import get_client_ip_address, IPAddressString


# Various events can have different parameters, represented as a metadata
# column in the DB.
# We model the events with Python types below, to make it easier to work with them.


@dataclasses.dataclass(frozen=True)
class UserEventBase:
    user: User
    ip_address: IPAddressString | None
    created_at: datetime.datetime


@dataclasses.dataclass(frozen=True)
class UserEventLogin(UserEventBase):
    pass


@dataclasses.dataclass(frozen=True)
class UserEventSubmit(UserEventBase):
    assigned_task_id: int
    submit_num: int


UserEvent = UserEventLogin | UserEventSubmit


class UserEventModel(models.Model):
    """
    Represents an action performed by a user.
    Records the IP address, the performed action, and the user who performed it.
    """

    class Meta:
        db_table = "common_user_event"
        verbose_name = "user event"

    class Action(models.TextChoices):
        Login = ("login", "Login")
        Submit = ("submit", "Submit")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=Action.choices)
    ip_address = models.GenericIPAddressField(null=True, verbose_name="IP address")
    # Arbitrary metadata that can be attached to each event
    metadata = JSONField("Metadata", null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} ({self.user.username}) at {self.created_at.strftime("%d. %m. %y %H:%M:%S")} from {self.ip_address}"

    def deserialize(self) -> UserEventBase | None:
        match self.action:
            case UserEventModel.Action.Login.value:
                return UserEventLogin(
                    user=self.user,
                    ip_address=IPAddressString(self.ip_address),
                    created_at=self.created_at,
                )
            case UserEventModel.Action.Submit.value:
                return UserEventSubmit(
                    user=self.user,
                    ip_address=IPAddressString(self.ip_address),
                    created_at=self.created_at,
                    assigned_task_id=self.metadata["task"],
                    submit_num=self.metadata["submit_num"],
                )
        logging.error(f"Invalid UserEvent action {self.action} found")
        return None


def record_login_event(request: HttpRequest, user: User):
    event = UserEventModel(
        user=user, action=UserEventModel.Action.Login, ip_address=get_client_ip_address(request)
    )
    event.save()


def record_submit_event(request: HttpRequest, user: User, task: "AssignedTask", submit_num: int):
    event = UserEventModel(
        user=user,
        action=UserEventModel.Action.Submit,
        metadata=dict(task=task.id, submit_num=submit_num),
        ip_address=get_client_ip_address(request),
    )
    event.save()
