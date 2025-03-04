from django.urls import path

from . import views
from common.inbus import views as inbus_views

urlpatterns = [
    path("tasks/<int:task_id>", views.task_detail),
    path("tasks/<int:task_id>/duplicate", views.duplicate_task),
    path("tasks/", views.task_detail),
    path("task-list", views.tasks_list_all),
    path("task-list/<subject_abbr>", views.tasks_list_all),
    path("student-list", views.student_list),
    path("submits/<int:task_assignment>", views.create_submit),
    path("info", views.info),
    path("classes", views.class_detail_list),
    path("classes/all", views.all_classes),
    path("classes/<int:class_id>/add_students", views.add_student_to_class),
    path("subject/<subject_abbr>", views.subject_list),
    path("subjects/all", views.subjects_all),
    path("teachers/all", views.teachers_all),
    path("reevaluate_task/<int:task_id>", views.reevaluate_task),
    path("search", views.search),
    path("transfer_students", views.transfer_students),
    path("semesters", views.semesters),
    path("import/activities", views.import_activities),
    path("inbus/subject_versions", inbus_views.subject_versions),
    path(
        "inbus/schedule/subject/version/<int:subject_version_id>/<int:inbus_semester_id>",
        inbus_views.schedule_subject_by_version_id,
    ),
    path(
        "inbus/schedule/students/activity/<int:concrete_activity_id>",
        inbus_views.students_in_concrete_activity,
    ),
    path("quiz/<int:quiz_id>", views.quiz_yaml, name="api_quiz_yaml"),
    path(
        "quiz/<int:quiz_id>/question/preview",
        views.quiz_question_preview,
        name="api_quiz_question_preview",
    ),
    path(
        "quiz/<int:enrolled_id>/result/<int:is_submit>", views.quiz_results, name="api_quiz_results"
    ),
    path("quiz/<int:enrolled_id>/scoring", views.quiz_scoring, name="api_quiz_scoring"),
    path("quiz/<int:quiz_id>/classes", views.quiz_classes, name="api_quiz_classes"),
    path("quiz/add", views.quiz_add, name="api_quiz_add"),
    path("quiz/<int:quiz_id>/duplicate", views.quiz_duplicate),
    path("quiz/<int:quiz_id>/assignments", views.quiz_assignments, name="api_quiz_assignments"),
]
