"""Production overrides."""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

_JSON_FORMAT = (
    '{"time":"%(asctime)s","level":"%(levelname)s",'
    '"logger":"%(name)s","msg":"%(message)s"}'
)
LOGGING["formatters"]["json"] = {  # noqa: F405
    "()": "logging.Formatter",
    "format": _JSON_FORMAT,
}
LOGGING["handlers"]["console"]["formatter"] = "json"  # noqa: F405
