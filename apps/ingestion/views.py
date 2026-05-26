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
from services import import_service


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
        job = import_service.create_import_job_from_upload(
            upload.validated_data["file"], request.user
        )
        return Response(ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def errors(self, request, pk=None):
        job = self.get_object()
        rows = ErrorQuarantine.objects.filter(import_job=job)
        page = self.paginate_queryset(rows)
        if page is not None:
            serializer = ErrorQuarantineSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(ErrorQuarantineSerializer(rows, many=True).data)
