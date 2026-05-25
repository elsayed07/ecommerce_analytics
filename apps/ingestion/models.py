from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class ImportJob(BaseModel):
    class Format(models.TextChoices):
        CSV = "csv", "CSV"
        JSON = "json", "JSON"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    source_filename = models.CharField(max_length=255)
    file_format = models.CharField(max_length=8, choices=Format.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    rows_processed = models.PositiveIntegerField(default=0)
    rows_failed = models.PositiveIntegerField(default=0)
    duration_seconds = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_jobs",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source_filename} ({self.status})"


class ErrorQuarantine(BaseModel):
    import_job = models.ForeignKey(
        ImportJob, on_delete=models.CASCADE, related_name="quarantined_rows"
    )
    row_number = models.PositiveIntegerField()
    reason = models.CharField(max_length=255)
    raw_data = models.JSONField(default=dict)

    class Meta:
        ordering = ["row_number"]
        indexes = [models.Index(fields=["import_job"])]

    def __str__(self):
        return f"row {self.row_number}: {self.reason}"
