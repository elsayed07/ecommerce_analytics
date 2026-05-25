import os

from django.core.management.base import BaseCommand, CommandError

from apps.ingestion.models import ImportJob
from services import import_service


class Command(BaseCommand):
    help = "Import an orders CSV/JSON file synchronously through the ETL pipeline."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to the CSV/JSON file.")

    def handle(self, *args, **options):
        path = options["file"]
        if not os.path.exists(path):
            raise CommandError(f"File not found: {path}")

        ext = os.path.splitext(path)[1].lower()
        if ext not in (".csv", ".json"):
            raise CommandError("Only .csv and .json files are supported.")

        file_format = ImportJob.Format.CSV if ext == ".csv" else ImportJob.Format.JSON
        job = ImportJob.objects.create(
            source_filename=os.path.basename(path), file_format=file_format
        )
        import_service.process_import_job(job, path)
        job.refresh_from_db()

        self.stdout.write(
            self.style.SUCCESS(
                f"Import {job.status}: {job.rows_processed} processed, "
                f"{job.rows_failed} failed (job #{job.pk})"
            )
        )
