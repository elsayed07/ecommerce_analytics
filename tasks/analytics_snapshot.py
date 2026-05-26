import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_analytics_snapshot(self):
    from services import analytics_service

    try:
        return analytics_service.build_snapshots()
    except Exception as exc:
        logger.error("Analytics snapshot build failed: %s", exc)
        raise self.retry(exc=exc) from exc
