import datetime
from typing import List

from django.contrib.auth.models import User

from .models import AssignedTask, Task

# needs-test
def get_active_exams_for_student_at(student: User, at_time: datetime.datetime) -> List[AssignedTask]:
    """
    Returns assigned tasks with the `Exam` type that are active (between start and deadline)
    at the specified time for the given `student`.
    """
    query = AssignedTask.objects.filter(
        task__type=Task.TaskType.EXAM.value,
        assigned__lte=at_time,
        deadline__isnull=False,
        deadline__gte=at_time,
        clazz__students__in=(student.id, )
    )
    return list(query.all())
