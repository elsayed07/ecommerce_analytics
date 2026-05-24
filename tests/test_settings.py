import importlib
import json
import logging

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.common.logging import JsonFormatter


def test_json_formatter_emits_valid_json():
    record = logging.LogRecord(
        name="app", level=logging.INFO, pathname=__file__, lineno=1,
        msg='quote " and newline \n', args=(), exc_info=None,
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app"
    assert payload["msg"] == 'quote " and newline \n'


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", "example.com")
    monkeypatch.setenv("SECRET_KEY", "baseline-key")

    prod = importlib.import_module("config.settings.production")
    importlib.reload(prod)  # baseline: loads fine while SECRET_KEY is set
    assert prod.SECRET_KEY == "baseline-key"

    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ImproperlyConfigured):
        importlib.reload(prod)
