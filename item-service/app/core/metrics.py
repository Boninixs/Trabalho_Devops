import time
from enum import Enum

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

METRICS_PATH = "/metrics"

HTTP_REQUESTS_TOTAL = Counter(
    "item_service_http_requests_total",
    "Total HTTP requests handled by item-service.",
    labelnames=("method", "path", "status_code"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "item_service_http_request_duration_seconds",
    "Latency of HTTP requests handled by item-service.",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "item_service_http_requests_in_progress",
    "Number of in-progress HTTP requests handled by item-service.",
)
ITEMS_CREATED_TOTAL = Counter(
    "item_service_items_created_total",
    "Total number of items successfully created by item-service.",
)
ITEM_STATUS_TRANSITIONS_TOTAL = Counter(
    "item_service_item_status_transitions_total",
    "Total committed item status transitions performed by item-service.",
    labelnames=("from_status", "to_status", "transition_mode"),
)
ITEM_EVENTS_ENQUEUED_TOTAL = Counter(
    "item_service_item_events_enqueued_total",
    "Total domain events enqueued into the item-service outbox.",
    labelnames=("event_type",),
)


def _normalize_status(status: Enum | str | None) -> str:
    if status is None:
        return "NONE"
    if isinstance(status, Enum):
        return str(status.value)
    return str(status)


def _resolve_path_template(request: Request) -> str:
    route = request.scope.get("route")
    path_template = getattr(route, "path", None)
    if isinstance(path_template, str):
        return path_template
    return request.url.path


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, metrics_path: str = METRICS_PATH) -> None:
        super().__init__(app)
        self.metrics_path = metrics_path

    async def dispatch(self, request: Request, call_next):
        if request.url.path == self.metrics_path:
            return await call_next(request)

        method = request.method
        HTTP_REQUESTS_IN_PROGRESS.inc()
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed_seconds = time.perf_counter() - start_time
            path = _resolve_path_template(request)
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(elapsed_seconds)
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status_code="500").inc()
            HTTP_REQUESTS_IN_PROGRESS.dec()
            raise

        elapsed_seconds = time.perf_counter() - start_time
        path = _resolve_path_template(request)
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(elapsed_seconds)
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            path=path,
            status_code=str(response.status_code),
        ).inc()
        HTTP_REQUESTS_IN_PROGRESS.dec()
        return response


def record_items_created(count: int = 1) -> None:
    ITEMS_CREATED_TOTAL.inc(count)


def record_item_status_transition(
    *,
    from_status: Enum | str | None,
    to_status: Enum | str,
    transition_mode: str,
    count: int = 1,
) -> None:
    ITEM_STATUS_TRANSITIONS_TOTAL.labels(
        from_status=_normalize_status(from_status),
        to_status=_normalize_status(to_status),
        transition_mode=transition_mode,
    ).inc(count)


def record_item_event_enqueued(*, event_type: str, count: int = 1) -> None:
    ITEM_EVENTS_ENQUEUED_TOTAL.labels(event_type=event_type).inc(count)


def register_metrics(app: FastAPI) -> None:
    app.add_middleware(PrometheusMetricsMiddleware, metrics_path=METRICS_PATH)

    def metrics_endpoint() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.add_api_route(
        METRICS_PATH,
        metrics_endpoint,
        methods=["GET"],
        include_in_schema=False,
        tags=["metrics"],
    )
