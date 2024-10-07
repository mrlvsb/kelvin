from django.urls import path

from . import views
from common.inbus import views as inbus_views

urlpatterns = [
    path("tasks/<int:task_id>", views.task_detail),
    path("tasks/<int:task_id>/duplicate", views.duplicate_task),
    path("tasks/", views.task_detail),
    path("tasks", views.tasks_list),
    path("task-list", views.tasks_list_all),
    path("task-list/<subject_abbr>", views.tasks_list_all),
    path("submits/<int:task_assignment>", views.create_submit),
    path("info", views.info),
    path("classes", views.class_detail_list),
    path("classes/all", views.all_classes),
    path("classes/<int:class_id>/add_students", views.add_student_to_class),
    path("subject/<subject_abbr>", views.subject_list),
    path("subjects/all", views.subjects_all),
    path("reevaluate_task/<int:task_id>", views.reevaluate_task),
    path("search", views.search),
    path("transfer_students", views.transfer_students),
    path("semesters", views.semesters),
    path("import/activities", views.import_activities),
    path("inbus/subject_versions", inbus_views.subject_versions),
    path(
        "inbus/schedule/subject/version/<int:subject_version_id>",
        inbus_views.schedule_subject_by_version_id,
    ),
    path(
        "inbus/schedule/students/activity/<int:concrete_activity_id>",
        inbus_views.students_in_concrete_activity,
    ),
]
