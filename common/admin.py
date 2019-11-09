from django.contrib import admin
import common.models as models
from django.contrib.auth.models import User


class ClassAdmin(admin.ModelAdmin):
    autocomplete_fields = ['students']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            kwargs["queryset"] = User.objects.filter(groups__name='teacher')
        print(db_field.name)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)



admin.site.register(models.Task)
admin.site.register(models.Class, ClassAdmin)
admin.site.register(models.Submit)
admin.site.register(models.AssignedTask)