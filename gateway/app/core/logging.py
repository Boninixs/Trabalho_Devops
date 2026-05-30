import json
import logging
import sys
import time
from contextvars import ContextVar
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="-")
service_name_ctx: ContextVar[str] = ContextVar("service_name", default="service")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": getattr(record, "service", service_name_ctx.get()),
            "correlation_id": getattr(
                record,
                "correlation_id",
                correlation_id_ctx.get(),
            ),
        }

        for field_name in ("method", "path", "status_code", "duration_ms"):
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(service_name: str, log_level: str) -> None:
    service_name_ctx.set(service_name)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        correlation_id = headers.get("X-Correlation-ID", str(uuid4()))
        token = correlation_id_ctx.set(correlation_id)
        logger = get_logger("http")
        start_time = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                mutable_headers = MutableHeaders(scope=message)
                mutable_headers["X-Correlation-ID"] = correlation_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "request_failed",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "duration_ms": duration_ms,
                },
            )
            correlation_id_ctx.reset(token)
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "request_completed",
            extra={
                "method": scope["method"],
                "path": scope["path"],
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
        correlation_id_ctx.reset(token)
