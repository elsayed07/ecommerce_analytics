from django.contrib import admin

from .models import ErrorQuarantine, ImportJob


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ["source_filename", "status", "rows_processed", "rows_failed", "created_at"]
    list_filter = ["status", "file_format"]


@admin.register(ErrorQuarantine)
class ErrorQuarantineAdmin(admin.ModelAdmin):
    list_display = ["import_job", "row_number", "reason"]
    list_filter = ["reason"]
