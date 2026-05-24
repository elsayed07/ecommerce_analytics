"""Production overrides."""
from .base import *  # noqa: F401,F403
from .base import LOGGING, env

# Required in production — no insecure fallback.
SECRET_KEY = env("SECRET_KEY")

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

LOGGING["formatters"]["json"] = {"()": "apps.common.logging.JsonFormatter"}
LOGGING["handlers"]["console"]["formatter"] = "json"
