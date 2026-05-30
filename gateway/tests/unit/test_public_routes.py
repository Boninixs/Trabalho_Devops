import asyncio
import json
from uuid import uuid4

import pytest

from app.api.public import block_internal_routes, items_collection
from app.core.exceptions import (
    DownstreamServiceTimeoutError,
    DownstreamServiceUnavailableError,
    GatewayAuthenticationError,
    InternalRouteBlockedError,
)
from app.main import (
    downstream_timeout_error_handler,
    downstream_unavailable_error_handler,
)
from app.schemas.auth import GatewayTokenClaims
from app.services.security import get_current_claims
from tests.conftest import build_access_token, build_request


def test_missing_token_is_rejected_on_protected_route() -> None:
    request = build_request("/api/items")

    with pytest.raises(GatewayAuthenticationError, match="Token de acesso ausente"):
        asyncio.run(get_current_claims(request))


def test_invalid_token_is_rejected_on_protected_route() -> None:
    request = build_request(
        "/api/items",
        headers={"Authorization": "Bearer invalid-token"},
    )

    with pytest.raises(GatewayAuthenticationError, match="Token inválido ou expirado"):
        asyncio.run(get_current_claims(request))


def test_internal_route_is_blocked() -> None:
    with pytest.raises(InternalRouteBlockedError, match="Rota interna não exposta"):
        asyncio.run(block_internal_routes("recovery/open"))


def test_timeout_handler_returns_504() -> None:
    response = asyncio.run(downstream_timeout_error_handler(None, DownstreamServiceTimeoutError("timeout")))

    assert response.status_code == 504
    assert json.loads(response.body)["detail"] == "timeout"


def test_unavailable_handler_returns_502() -> None:
    response = asyncio.run(
        downstream_unavailable_error_handler(None, DownstreamServiceUnavailableError("unavailable")),
    )

    assert response.status_code == 502
    assert json.loads(response.body)["detail"] == "unavailable"


def test_protected_route_forwards_when_claims_are_present(fake_proxy_service) -> None:
    request = build_request(
        "/api/items",
        headers={
            "Authorization": f"Bearer {build_access_token()}",
            "X-Correlation-ID": "corr-unit-2",
        },
    )
    claims = GatewayTokenClaims(sub=uuid4(), role="USER", exp=9999999999)

    response = asyncio.run(
        items_collection(
            request=request,
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    )

    assert response.status_code == 200
    assert fake_proxy_service.calls[0]["service_name"] == "item"
    assert fake_proxy_service.calls[0]["upstream_path"] == "/items"
