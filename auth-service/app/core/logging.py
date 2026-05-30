"""
Esse arquivo é responsável pela configuração de logging e rastreio de requisições.
"""
import json
import logging
import sys
import time
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

correlation_id_ctx: ContextVar[str] = ContextVar(
    "correlation_id", 
    default="-",
)
service_name_ctx: ContextVar[str] = ContextVar(
    "service_name", default="service",
)


class JsonFormatter(logging.Formatter):
    """
    Formatter de logs em formato JSON.
    """
    def format(self, record: logging.LogRecord) -> str:
        """"
        Formata o log como JSON, incluindo campos adicionais como correlation_id e service.
        args:
            record: LogRecord a ser formatado.
        Returns:
            String JSON formatada.
        """
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
    """
    Configura o logging global da aplicação.
    Args:
        service_name: Nome do serviço.
        log_level: Nível de log.
    Returns:
        None
    """
    service_name_ctx.set(service_name)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())


def get_logger(name: str) -> logging.Logger:
    """
    Retorna um logger nomeado.

    Args:
        name: Nome do logger.

    Returns:
        Instância de logger.
    """
    return logging.getLogger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para logging de requisições HTTP.
    """
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
        token = correlation_id_ctx.set(correlation_id)
        logger = get_logger("http")
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            correlation_id_ctx.reset(token)
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Correlation-ID"] = correlation_id
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        correlation_id_ctx.reset(token)
        return response

