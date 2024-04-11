from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

import common.models as models
import common.utils


class BaseByTeacherFilter(admin.SimpleListFilter):
    """
    Base class to filter by Teacher.

    From: https://books.agiliq.com/projects/django-admin-cookbook/en/latest/filtering_calculated_fields.html
    and https://stackoverflow.com/questions/880684/in-django-admin-how-to-filter-users-by-group
    """
    title = 'teacher'
    parameter_name = 'teacher'

    def lookups(self, request, model_admin):
        teachers = User.objects.filter(groups__name='teachers')
        items = ( (t.pk, t.username) for t in teachers )

        return items

    def queryset(self, request, queryset):
        pass


class ByClassTeacherFilter(BaseByTeacherFilter):

    def queryset(self, request, queryset):
        # If 'All' is chosen in the admin, self.value() is None
        value = self.value()
        if value:
            return queryset.filter(teacher__pk=value)
        else:
            return queryset


class ClassAdmin(admin.ModelAdmin):
    autocomplete_fields = ['students']
    list_filter = (ByClassTeacherFilter, 'subject')
    list_display = admin.ModelAdmin.list_display + ('teacher_name',)
    search_fields = ['subject__abbr']
    save_as = True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            kwargs["queryset"] = User.objects.filter(groups__name='teachers').order_by('username')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def teacher_name(self, obj):
        if obj.teacher:
            teacher = obj.teacher
            return f'{teacher.get_full_name()} ({teacher.username})'
        else:
            return '-'


class ByAssignedTaskTeacherFilter(BaseByTeacherFilter):

    def queryset(self, request, queryset):
        # If 'All' is chosen in the admin, self.value() is None
        value = self.value()
        if value:
            return queryset.filter(clazz__teacher__pk=value)
        else:
            return queryset


class AssignedTaskAdmin(admin.ModelAdmin):
    # to see directly the teacher
    list_display = admin.ModelAdmin.list_display + ('teacher_name', 'clazz', 'assigned', 'deadline')

    # to filter by teacher
    list_filter = ('clazz__subject', 'task__name', ByAssignedTaskTeacherFilter, 'clazz',)

    autocomplete_fields = ['task', 'clazz']
    search_fields = ['task__name', 'clazz__teacher__username', 'clazz__subject_abbr']


    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "clazz":
            kwargs["queryset"] = models.Class.objects.current_semester()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def teacher_name(self, obj):
        teacher = obj.clazz.teacher
        return f'{teacher.get_full_name()} ({teacher.username})'


class IsTeacherFilter(admin.SimpleListFilter):
    """
    From: https://books.agiliq.com/projects/django-admin-cookbook/en/latest/filtering_calculated_fields.html
    and https://stackoverflow.com/questions/880684/in-django-admin-how-to-filter-users-by-group
    """
    title = 'is teacher'
    parameter_name = 'is_teacher'

    def lookups(self, request, model_admin):
        return (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )
        #items = ()
        #for group in Group.objects.all():
        #    items += ((str(group.id), str(group.name),),)
        #return items

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'Yes':
            return queryset.filter(groups__name='teachers')
        elif value == 'No':
            return queryset.exclude(groups__name='teachers')
        return queryset

class MyUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ('is_teacher',)
    list_filter = UserAdmin.list_filter + (IsTeacherFilter,)

    def is_teacher(self, obj):
        return common.utils.is_teacher(obj)

class TaskAdmin(admin.ModelAdmin):
    list_filter = ('subject', )
    search_fields = ['name', 'subject__abbr']

class SubmitAdmin(admin.ModelAdmin):
    list_filter = ('assignment__task__subject', 'assignment__task__name')
    autocomplete_fields = ['assignment']

admin.site.register(models.Task, TaskAdmin)
admin.site.register(models.Class, ClassAdmin)
admin.site.register(models.Submit, SubmitAdmin)
admin.site.register(models.AssignedTask, AssignedTaskAdmin)
admin.site.register(models.Semester)
admin.site.register(models.Subject)

admin.site.unregister(User)
admin.site.register(User, MyUserAdmin)

admin.site.site_header = 'Kelvin administration'
admin.site.site_title = 'Kelvin administration'
