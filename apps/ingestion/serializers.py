import os

from django.conf import settings
from rest_framework import serializers

from apps.ingestion.models import ErrorQuarantine, ImportJob

ALLOWED_EXTENSIONS = (".csv", ".json")
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/json",
    "text/plain",
    "application/octet-stream",
}


class ImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJob
        fields = [
            "id",
            "source_filename",
            "file_format",
            "status",
            "started_at",
            "finished_at",
            "rows_processed",
            "rows_failed",
            "duration_seconds",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields


class ErrorQuarantineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ErrorQuarantine
        fields = ["id", "row_number", "reason", "raw_data"]


class ImportUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError("Only .csv and .json files are accepted.")
        if value.size > settings.MAX_IMPORT_BYTES:
            raise serializers.ValidationError("File exceeds the 10MB limit.")
        if value.content_type and value.content_type not in ALLOWED_MIME_TYPES:
            raise serializers.ValidationError(
                f"Unsupported content type: {value.content_type}"
            )
        return value
