"""Logging setup: a request ID on every line, as text or JSON (for log aggregators)."""
import json
import logging
import re
import uuid
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar("request_id", default="-")

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def new_request_id(incoming: str | None) -> str:
    """Keep a well-formed ID from the client or proxy (so logs line up end to end), else make one."""
    if incoming and _VALID_REQUEST_ID.match(incoming):
        return incoming
    return uuid.uuid4().hex


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(fmt: str = "text", level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
