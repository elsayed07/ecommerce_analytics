"""Shared settings for all environments. Env-driven; never hardcode secrets."""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env("SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# Optional link surfaced on the landing page; omitted when empty.
GITHUB_REPO_URL = env("GITHUB_REPO_URL", default="")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.common",
    "apps.users",
    "apps.products",
    "apps.orders",
    "apps.ingestion",
    "apps.analytics",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.APIErrorMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="ecommerce_analytics"),
        "USER": env("POSTGRES_USER", default="postgres"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="postgres"),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env("POSTGRES_PORT", default="5432"),
    }
}

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "apps.common.renderers.EnvelopeJSONRenderer",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/min",
        "user": "1000/day",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "E-Commerce Analytics API",
    "DESCRIPTION": "REST API for the e-commerce analytics dashboard.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Celery ---
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "nightly-import": {
        "task": "tasks.nightly_import.run_nightly_import",
        "schedule": crontab(hour=2, minute=0),
    },
    "analytics-snapshot": {
        "task": "tasks.analytics_snapshot.run_analytics_snapshot",
        "schedule": crontab(hour=3, minute=0),
    },
}

# --- Ingestion / ETL ---
IMPORT_INBOX_DIR = env("IMPORT_INBOX_DIR", default=str(BASE_DIR / "data" / "inbox"))
MAX_IMPORT_BYTES = 10 * 1024 * 1024
FX_RATES_TO_EUR = {
    "EUR": Decimal("1.00"),
    "USD": Decimal("0.92"),
    "GBP": Decimal("1.17"),
    "CHF": Decimal("1.05"),
}

# --- Forecasting ---
FORECAST_HORIZON_DAYS = env.int("FORECAST_HORIZON_DAYS", default=30)
ANOMALY_Z_THRESHOLD = env.float("ANOMALY_Z_THRESHOLD", default=3.0)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
