from django.contrib.auth.decorators import login_required, user_passes_test

from .teacher import teacher_list
from .student import student_index
from common.utils import is_teacher

@login_required()
def index(request):
    if is_teacher(request.user):
        return teacher_list(request, teacher__pk=request.user.id)
    return student_index(request)

def template_context(request):
    return {
        'is_teacher': is_teacher(request.user),
    }
