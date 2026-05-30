from starlette.requests import Request

from app.core.logging import correlation_id_ctx
from app.services.proxy_service import GatewayProxyService


def test_proxy_service_propagates_authorization_and_correlation_headers() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/items",
        "headers": [
            (b"authorization", b"Bearer test-token"),
            (b"accept", b"application/json"),
        ],
        "query_string": b"",
    }
    token = correlation_id_ctx.set("corr-unit-1")
    try:
        request = Request(scope)
        proxy_service = GatewayProxyService(base_urls={"item": "http://item-service:8000"})

        headers = proxy_service._build_downstream_headers(request)
    finally:
        correlation_id_ctx.reset(token)

    assert headers["authorization"] == "Bearer test-token"
    assert headers["X-Correlation-ID"] == "corr-unit-1"
    assert headers["accept"] == "application/json"
