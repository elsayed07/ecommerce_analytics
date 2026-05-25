import logging

import redis
from django.conf import settings
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def _check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return "ok"
    except Exception as exc:
        logger.warning("Health check: database unreachable: %s", exc)
        return "error"


def _check_redis():
    try:
        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        client.ping()
        return "ok"
    except Exception as exc:
        logger.warning("Health check: redis unreachable: %s", exc)
        return "error"


def health(request):
    components = {"database": _check_database(), "redis": _check_redis()}
    healthy = all(status == "ok" for status in components.values())
    body = {"status": "ok" if healthy else "error", **components}
    return JsonResponse(body, status=200 if healthy else 503)
