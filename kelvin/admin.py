from django.contrib import admin
import kelvin.models as models

admin.site.register(models.Task)
admin.site.register(models.Class)
admin.site.register(models.Submit)
admin.site.register(models.TaskInClass)