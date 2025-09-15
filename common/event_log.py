import dataclasses
import datetime
import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import caches
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


@dataclasses.dataclass(frozen=True)
class UserEventTaskDisplayed(UserEventBase):
    assigned_task_id: int


@dataclasses.dataclass(frozen=True)
class UserEventFinalSubmit(UserEventBase):
    assigned_task_id: int
    submit_num: int


UserEvent = UserEventLogin | UserEventSubmit | UserEventTaskDisplayed | UserEventFinalSubmit


class UserEventModel(models.Model):
    """
    Represents an action performed by a user.
    Records the IP address, the performed action, and the user who performed it.
    """

    class Meta:
        db_table = "common_user_event"
        verbose_name = "user event"

    class Action(models.TextChoices):
        # A user has logged in
        Login = ("login", "Login")
        # A user has uploaded a submit
        Submit = ("submit", "Submit")
        # A user has displayed an assigned task
        TaskDisplayed = ("task-view", "Task displayed")
        # A user has marked submit as final
        SubmitMarkedAsFinal = ("final-submit", "Submit marked as final")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=15, choices=Action.choices)
    ip_address = models.GenericIPAddressField(null=True, verbose_name="IP address")
    # Arbitrary metadata that can be attached to each event
    metadata = JSONField("Metadata", null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} ({self.user.username}) at {self.created_at.strftime("%d. %m. %y %H:%M:%S")} from {self.ip_address}"

    def deserialize(self) -> UserEventBase | None:
        shared = dict(
            user=self.user, ip_address=IPAddressString(self.ip_address), created_at=self.created_at
        )
        match self.action:
            case UserEventModel.Action.Login.value:
                return UserEventLogin(**shared)
            case UserEventModel.Action.Submit.value:
                return UserEventSubmit(
                    **shared,
                    assigned_task_id=self.metadata["task"],
                    submit_num=self.metadata["submit_num"],
                )
            case UserEventModel.Action.TaskDisplayed.value:
                return UserEventTaskDisplayed(
                    **shared,
                    assigned_task_id=self.metadata["task"],
                )
            case UserEventModel.Action.SubmitMarkedAsFinal.value:
                return UserEventFinalSubmit(
                    **shared,
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


def record_final_submit_event(
    request: HttpRequest, user: User, task: "AssignedTask", submit_num: int
):
    event = UserEventModel(
        user=user,
        action=UserEventModel.Action.SubmitMarkedAsFinal,
        metadata=dict(task=task.id, submit_num=submit_num),
        ip_address=get_client_ip_address(request),
    )
    event.save()


# How long should we wait before recording two task display events for the same user
TASK_DISPLAYED_CACHE_TIMEOUT_SECONDS = 60 * 60


def record_task_displayed(request: HttpRequest, user: User, task: "AssignedTask"):
    """
    This functions records an event of a user displaying the assignment of a specific task.
    Since this event can happen very often and is on an otherwise "read-only" path, we sample
    the events to avoid overloading the DB.
    """

    ip_address = get_client_ip_address(request) or "unknown"

    # If the same user with the same IP displays the same task, it is considered to be the same
    # event.
    cache_key = ("task-view-event", user.username, ip_address, task.id)
    cache = caches["default"]
    entry = cache.get(cache_key)
    if entry is not None:
        # We have already recently logged this event, do nothing
        return

    event = UserEventModel(
        user=user,
        action=UserEventModel.Action.TaskDisplayed,
        metadata=dict(task=task.id),
        ip_address=ip_address,
    )
    event.save()

    # We use a dummy value, the presence of the key is the main information
    cache.set(cache_key, value=True, timeout=TASK_DISPLAYED_CACHE_TIMEOUT_SECONDS)
