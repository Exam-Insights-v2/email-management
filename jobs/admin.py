from django.contrib import admin

from .models import Job, Task


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "account")
    list_filter = ("status", "account")
    search_fields = ("title", "description")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "account", "job")
    list_filter = ("status", "priority")
    search_fields = ("title", "description")
