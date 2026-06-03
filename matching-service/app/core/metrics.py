import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

METRICS_PATH = "/metrics"

HTTP_REQUESTS_TOTAL = Counter(
    "matching_service_http_requests_total",
    "Total HTTP requests handled by matching-service.",
    labelnames=("method", "path", "status_code"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "matching_service_http_request_duration_seconds",
    "Latency of HTTP requests handled by matching-service.",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "matching_service_http_requests_in_progress",
    "Number of in-progress HTTP requests handled by matching-service.",
)
ITEM_EVENTS_CONSUMED_TOTAL = Counter(
    "matching_service_item_events_consumed_total",
    "Total item domain events consumed by matching-service.",
    labelnames=("event_type", "result"),
)
MATCHES_SUGGESTED_TOTAL = Counter(
    "matching_service_matches_suggested_total",
    "Total match suggestions created or reactivated by matching-service.",
)
MATCH_DECISIONS_TOTAL = Counter(
    "matching_service_match_decisions_total",
    "Total match decisions registered by matching-service.",
    labelnames=("decision",),
)
MATCH_EVENTS_ENQUEUED_TOTAL = Counter(
    "matching_service_match_events_enqueued_total",
    "Total match domain events enqueued into the matching-service outbox.",
    labelnames=("event_type",),
)


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


def record_item_event_consumed(*, event_type: str, result: str, count: int = 1) -> None:
    ITEM_EVENTS_CONSUMED_TOTAL.labels(event_type=event_type, result=result).inc(count)


def record_matches_suggested(count: int = 1) -> None:
    MATCHES_SUGGESTED_TOTAL.inc(count)


def record_match_decision(*, decision: str, count: int = 1) -> None:
    MATCH_DECISIONS_TOTAL.labels(decision=decision).inc(count)


def record_match_event_enqueued(*, event_type: str, count: int = 1) -> None:
    MATCH_EVENTS_ENQUEUED_TOTAL.labels(event_type=event_type).inc(count)


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
