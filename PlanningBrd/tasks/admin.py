from django.contrib import admin
from .models import Calendar, Project, Task, Reminder, Todo

# Register your models here.

admin.site.register(Calendar)
admin.site.register(Project)
admin.site.register(Task)
admin.site.register(Reminder)
admin.site.register(Todo)
