"""JSON logs with a per-request ID carried in a context variable.

Every record is one JSON object. Pipeline steps log an `event` name plus structured fields
(`log_event`), so one request's records can be pulled out by `request_id` and read in order
(`scripts/explain.py`). The request ID comes from a valid `x-request-id` header (so the Next
proxy and the backend share one ID) or is generated, and is echoed back in the response.
"""

import json
import logging
import re
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# A client-supplied ID goes into every log line, so only a plain token is accepted.
REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "msg": record.getMessage(),
        }
        # Structured fields: logger.info("msg", extra={"fields": {...}}).
        payload.update(getattr(record, "fields", None) or {})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str, log_file: str | None = None) -> None:
    """Logs to stderr; with `log_file`, also appends the same JSON lines to that file."""
    formatter = JsonFormatter()
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers[:] = handlers
    root.setLevel(level.upper())


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """One structured pipeline record, e.g. log_event(logger, "search.rerank", ranked=10)."""
    logger.info(event, extra={"fields": {"event": event, **fields}})


class RequestIdMiddleware:
    """Pure ASGI, so the ID stays set while a streamed (SSE) body is still being produced;
    Starlette's BaseHTTPMiddleware resets it as soon as the response headers are out."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if REQUEST_ID.match(incoming) else uuid.uuid4().hex

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"] = [
                    *(h for h in message["headers"] if h[0].lower() != b"x-request-id"),
                    (b"x-request-id", rid.encode()),
                ]
            await send(message)

        token = request_id_var.set(rid)
        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)
