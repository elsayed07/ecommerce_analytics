import os

from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.common.permissions import IsAdminOrAnalyst
from apps.ingestion.models import ErrorQuarantine, ImportJob
from apps.ingestion.serializers import (
    ErrorQuarantineSerializer,
    ImportJobSerializer,
    ImportUploadSerializer,
)
from tasks.nightly_import import process_import_job_task


class ImportJobViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ImportJob.objects.all()
    serializer_class = ImportJobSerializer
    permission_classes = [IsAdminOrAnalyst]
    parser_classes = [MultiPartParser, FormParser]
    ordering_fields = ["created_at", "status"]
    ordering = ["-created_at"]

    def create(self, request, *args, **kwargs):
        upload = ImportUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        uploaded = upload.validated_data["file"]

        ext = os.path.splitext(uploaded.name)[1].lower()
        file_format = (
            ImportJob.Format.CSV if ext == ".csv" else ImportJob.Format.JSON
        )

        job = ImportJob.objects.create(
            source_filename=uploaded.name,
            file_format=file_format,
            created_by=request.user,
        )

        import_dir = os.path.join(settings.MEDIA_ROOT, "imports")
        os.makedirs(import_dir, exist_ok=True)
        dest = os.path.join(import_dir, f"{job.pk}_{uploaded.name}")
        with open(dest, "wb") as out:
            for chunk in uploaded.chunks():
                out.write(chunk)

        process_import_job_task.delay(job.pk, dest)
        job.refresh_from_db()
        return Response(
            ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED
        )

    @action(detail=True, methods=["get"])
    def errors(self, request, pk=None):
        job = self.get_object()
        rows = ErrorQuarantine.objects.filter(import_job=job)
        page = self.paginate_queryset(rows)
        if page is not None:
            serializer = ErrorQuarantineSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(ErrorQuarantineSerializer(rows, many=True).data)
