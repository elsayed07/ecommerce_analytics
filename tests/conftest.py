import pytest


@pytest.fixture(autouse=True)
def celery_eager(settings):
    """Run Celery tasks inline so upload-triggered imports execute during tests."""
    from config import celery_app

    settings.CELERY_TASK_ALWAYS_EAGER = True
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True


@pytest.fixture(autouse=True)
def isolated_cache(settings):
    """Use an isolated in-memory cache per test (no Redis dependency, no leakage)."""
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
