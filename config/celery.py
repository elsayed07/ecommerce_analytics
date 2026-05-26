import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Register the top-level tasks package (not a Django app, so autodiscover misses it).
import tasks.analytics_snapshot  # noqa: E402,F401
import tasks.nightly_import  # noqa: E402,F401
