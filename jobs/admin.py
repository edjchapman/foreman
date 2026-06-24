from django.contrib import admin

from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["id", "job_type", "status", "progress", "attempts", "created_at"]
    list_filter = ["status", "job_type"]
    search_fields = ["id", "idempotency_key"]
    readonly_fields = ["id", "created_at", "updated_at"]
