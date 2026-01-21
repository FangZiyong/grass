from django.contrib import admin

from apps.execution.models.task_log import TaskRunLog
from apps.execution.models.task_run import TaskRunInstance


@admin.register(TaskRunInstance)
class TaskRunInstanceAdmin(admin.ModelAdmin):
    list_display = (
        "task_run_id",
        "task_type",
        "task_id",
        "tenant_id",
        "status",
        "started_at",
        "finished_at",
    )
    search_fields = ("task_type", "task_id", "tenant_id", "request_id", "worker_id")
    list_filter = ("status", "task_type")
    ordering = ("-task_run_id",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(TaskRunLog)
class TaskRunLogAdmin(admin.ModelAdmin):
    list_display = ("task_run_log_id", "task_run_id", "level", "created_at")
    search_fields = ("task_run_id", "message")
    list_filter = ("level",)
    ordering = ("-task_run_log_id",)
    readonly_fields = ("created_at",)
