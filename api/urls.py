from django.urls import path

from .views import default as default_view
from .views import quiz as quiz_view
from common.inbus import views as inbus_views

urlpatterns = [
    path("tasks/<int:task_id>", default_view.task_detail),
    path("tasks/<int:task_id>/duplicate", default_view.duplicate_task),
    path("tasks/", default_view.task_detail),
    path("classrooms-list/", default_view.classrooms_list),
    path("task-list", default_view.tasks_list_all),
    path("task-list/<subject_abbr>", default_view.tasks_list_all),
    path("student-list", default_view.student_list),
    path("submits/<int:task_assignment>", default_view.create_submit),
    path("info", default_view.info),
    path("classes", default_view.class_detail_list),
    path("classes/all", default_view.all_classes),
    path("classes/<int:class_id>/add_students", default_view.add_student_to_class),
    path("events/<login>", default_view.event_list),
    path("subject/<subject_abbr>", default_view.subject_list),
    path("subjects/all", default_view.subjects_all),
    path("teachers/all", default_view.teachers_all),
    path("reevaluate_task/<int:task_id>", default_view.reevaluate_task),
    path("transfer_students", default_view.transfer_students),
    path("semesters", default_view.semesters),
    path("import/activities", default_view.import_activities),
    path("inbus/subject_versions", inbus_views.subject_versions),
    path(
        "inbus/schedule/subject/version/<int:subject_version_id>/<int:inbus_semester_id>",
        inbus_views.schedule_subject_by_version_id,
    ),
    path(
        "inbus/schedule/students/activity/<int:concrete_activity_id>",
        inbus_views.students_in_concrete_activity,
    ),
    path("quiz/<int:quiz_id>", quiz_view.quiz_yaml, name="api_quiz_yaml"),
    path(
        "quiz/<int:quiz_id>/question/preview",
        quiz_view.quiz_question_preview,
        name="api_quiz_question_preview",
    ),
    path(
        "quiz/<int:enrolled_id>/result/<int:is_submit>",
        quiz_view.quiz_results,
        name="api_quiz_results",
    ),
    path("quiz/<int:enrolled_id>/scoring", quiz_view.quiz_scoring, name="api_quiz_scoring"),
    path("quiz/<int:quiz_id>/classes", quiz_view.quiz_classes, name="api_quiz_classes"),
    path("quiz/add", quiz_view.quiz_add, name="api_quiz_add"),
    path("quiz/enroll/<int:assigned_quiz_id>", quiz_view.quiz_enroll, name="api_quiz_enroll"),
    path("quiz/<int:quiz_id>/duplicate", quiz_view.quiz_duplicate),
    path("quiz/<int:quiz_id>/assignments", quiz_view.quiz_assignments, name="api_quiz_assignments"),
    path("quiz/<int:quiz_id>/submits", quiz_view.quiz_submits, name="api_quiz_submits_list"),
    path(
        "quiz/<int:quiz_id>/submits/<class_id>",
        quiz_view.quiz_submits,
        name="api_quiz_submits_list_class",
    ),
    path("quiz-list", quiz_view.quizzes_list_all, name="api_quiz_list"),
    path("quiz-list/<subject_abbr>", quiz_view.quizzes_list_all, name="api_quiz_list_subject"),
    path("health", default_view.health_check),
]
