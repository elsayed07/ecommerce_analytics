import logging

from django.http import JsonResponse

logger = logging.getLogger(__name__)


class APIErrorMiddleware:
    """Return the standard error envelope for unhandled exceptions under /api/v1/.

    DRF's exception handler only shapes known API exceptions; anything it doesn't
    handle would otherwise fall through to Django's default error page. This keeps
    API responses consistent without leaking exception details.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not request.path.startswith("/api/v1/"):
            return None
        logger.exception("Unhandled API exception at %s", request.path)
        return JsonResponse(
            {
                "success": False,
                "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"},
            },
            status=500,
        )
