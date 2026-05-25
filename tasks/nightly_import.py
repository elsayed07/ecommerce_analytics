import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_nightly_import(self):
    from services import import_service

    try:
        jobs = import_service.run_scheduled_import()
        return [job.pk for job in jobs]
    except Exception as exc:
        logger.error("Nightly import failed: %s", exc)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_import_job_task(self, job_id, file_path):
    from apps.ingestion.models import ImportJob
    from services import import_service

    try:
        job = ImportJob.objects.get(pk=job_id)
        import_service.process_import_job(job, file_path)
        return job_id
    except Exception as exc:
        logger.error("Import job %s task failed: %s", job_id, exc)
        raise self.retry(exc=exc) from exc
