import datetime
from typing import List

from django.contrib.auth.models import User

from .models import AssignedTask, Task


def get_active_exams_at(
    student: User, at_time: datetime.datetime, buffer: datetime.timedelta
) -> List[AssignedTask]:
    """
    Returns the *active* assigned tasks with the `Exam` task type.
    Time when an exam is considered to be *active* is the time range [assigned_at - buffer, deadline + buffer].
    If this time range overlaps with `at_time`, the exam is considered to be active.

    This can be used to figure out if a given student is "just before" or "just after" an exam.

    For example, let's say that an exam starts at 5PM and ends at 7PM, and the buffer is one hour.
    Then below:
              ####--|---|--####
                  4 5 6 7 8
    # marks time when the exam is not active
    - marks time when the exam is active
    | marks time when the exam is assigned
    """
    query = AssignedTask.objects.filter(
        task__type=Task.TaskType.EXAM.value,
        assigned__lte=at_time + buffer,
        deadline__isnull=False,
        deadline__gte=at_time - buffer,
        clazz__students__in=(student.id,),
    )
    return list(query.all())
