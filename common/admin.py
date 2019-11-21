from django.contrib import admin
import common.models as models
from django.contrib.auth.models import User


class ClassAdmin(admin.ModelAdmin):
    autocomplete_fields = ['students']
    list_filter = ('teacher',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            kwargs["queryset"] = User.objects.filter(groups__name='teachers')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AssignedTaskAdmin(admin.ModelAdmin):
    list_filter = ('clazz', 'task',)


admin.site.register(models.Task)
admin.site.register(models.Class, ClassAdmin)
admin.site.register(models.Submit)
admin.site.register(models.AssignedTask, AssignedTaskAdmin)

admin.site.site_header = 'Kelvin administration'
admin.site.site_title = 'Kelvin administration'
