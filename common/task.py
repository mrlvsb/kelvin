import datetime
from typing import List

from django.contrib.auth.models import User

from .models import AssignedTask, Task


def get_active_tasks_at(
    student: User, at_time: datetime.datetime, buffer: datetime.timedelta, type: Task.TaskType
) -> List[AssignedTask]:
    """
    Returns the *active* assigned tasks with the given task type.
    Time when a task is considered to be *active* is the time range [assigned_at - buffer, deadline + buffer].
    If this time range overlaps with `at_time`, the task is considered to be active.

    This can be used to figure out if a given student is "just before" or "just after" a task.

    For example, let's say that a task starts at 5PM and ends at 7PM, and the buffer is one hour.
    Then below:
              ####--|---|--####
                  4 5 6 7 8
    # marks time when the task is not active
    - marks time when the task is active
    | marks time when the task is assigned
    """
    query = AssignedTask.objects.filter(
        task__type=type,
        assigned__lte=at_time + buffer,
        deadline__isnull=False,
        deadline__gte=at_time - buffer,
        clazz__students__in=(student.id,),
    )
    return list(query.all())
