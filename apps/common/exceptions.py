from rest_framework.views import exception_handler

STATUS_TO_CODE = {
    400: "VALIDATION_ERROR",
    401: "AUTHENTICATION_FAILED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    429: "RATE_LIMITED",
}


def _error_code(status_code):
    if status_code in STATUS_TO_CODE:
        return STATUS_TO_CODE[status_code]
    if status_code >= 500:
        return "INTERNAL_ERROR"
    return "ERROR"


def _message(data):
    if isinstance(data, dict):
        if "detail" in data:
            return str(data["detail"])
        parts = []
        for field, errors in data.items():
            first = errors[0] if isinstance(errors, (list, tuple)) and errors else errors
            parts.append(f"{field}: {first}")
        return "; ".join(parts) if parts else "Error"
    if isinstance(data, (list, tuple)) and data:
        return str(data[0])
    return str(data)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    response.data = {
        "success": False,
        "error": {
            "code": _error_code(response.status_code),
            "message": _message(response.data),
        },
    }
    return response
