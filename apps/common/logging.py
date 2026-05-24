import json
import logging


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single valid JSON object."""

    def format(self, record):
        payload = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)
