from django.contrib import admin
import common.models as models
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin


class ClassAdmin(admin.ModelAdmin):
    autocomplete_fields = ['students']
    # FIXME: Limit to teachers only, now shows any User
    list_filter = ('teacher',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            kwargs["queryset"] = User.objects.filter(groups__name='teachers')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AssignedTaskAdmin(admin.ModelAdmin):
    list_filter = ('clazz', 'task',)
    # FIXME: Probably doesn't work witk foreign keys
    #list_filter = ('clazz', 'task',)
    list_filter = ('task__name', 'clazz__teacher',)


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
        return obj.groups.filter(name='teachers').exists()

admin.site.register(models.Task)
admin.site.register(models.Class, ClassAdmin)
admin.site.register(models.Submit)
admin.site.register(models.AssignedTask, AssignedTaskAdmin)

admin.site.unregister(User)
admin.site.register(User, MyUserAdmin)

admin.site.site_header = 'Kelvin administration'
admin.site.site_title = 'Kelvin administration'
