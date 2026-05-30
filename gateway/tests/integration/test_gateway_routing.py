import asyncio
import json
from uuid import uuid4

import pytest
from starlette.responses import JSONResponse

from app.api.public import (
    auth_login,
    auth_me,
    auth_register,
    item_history_resource,
    item_resource,
    item_status_resource,
    items_collection,
    match_accept,
    match_reject,
    match_resource,
    matches_collection,
    recovery_case_cancel,
    recovery_case_complete,
    recovery_case_resource,
    recovery_cases_collection,
)
from app.main import downstream_timeout_error_handler, downstream_unavailable_error_handler
from app.schemas.auth import GatewayTokenClaims
from tests.conftest import build_access_token, build_request


pytestmark = pytest.mark.integration


def build_claims() -> GatewayTokenClaims:
    return GatewayTokenClaims(sub=uuid4(), role="USER", exp=9999999999)


def test_auth_routes_are_forwarded(fake_proxy_service) -> None:
    fake_proxy_service.responses[("auth", "POST", "/auth/register")] = JSONResponse(
        status_code=201,
        content={"id": "u1"},
    )
    fake_proxy_service.responses[("auth", "POST", "/auth/login")] = JSONResponse(
        status_code=200,
        content={"access_token": "token"},
    )
    fake_proxy_service.responses[("auth", "GET", "/auth/me")] = JSONResponse(
        status_code=200,
        content={"id": "u1", "role": "USER"},
    )

    register_response = asyncio.run(
        auth_register(
            request=build_request(
                "/api/auth/register",
                method="POST",
                json_body={"full_name": "User One", "email": "user@example.com", "password": "Password123"},
            ),
            proxy_service=fake_proxy_service,
        ),
    )
    login_response = asyncio.run(
        auth_login(
            request=build_request(
                "/api/auth/login",
                method="POST",
                json_body={"email": "user@example.com", "password": "Password123"},
            ),
            proxy_service=fake_proxy_service,
        ),
    )
    me_response = asyncio.run(
        auth_me(
            request=build_request(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {build_access_token()}"},
            ),
            _claims=build_claims(),
            proxy_service=fake_proxy_service,
        ),
    )

    assert register_response.status_code == 201
    assert login_response.status_code == 200
    assert me_response.status_code == 200
    assert [call["upstream_path"] for call in fake_proxy_service.calls] == [
        "/auth/register",
        "/auth/login",
        "/auth/me",
    ]


def test_item_routes_are_forwarded(fake_proxy_service) -> None:
    fake_proxy_service.responses[("item", "GET", "/items")] = JSONResponse(status_code=200, content=[])
    fake_proxy_service.responses[("item", "GET", "/items/item-1")] = JSONResponse(status_code=200, content={"id": "item-1"})
    fake_proxy_service.responses[("item", "PATCH", "/items/item-1/status")] = JSONResponse(
        status_code=200,
        content={"id": "item-1", "status": "MATCHED"},
    )
    fake_proxy_service.responses[("item", "GET", "/items/item-1/history")] = JSONResponse(status_code=200, content=[])

    claims = build_claims()
    list_response = asyncio.run(
        items_collection(
            request=build_request(
                "/api/items",
                headers={"Authorization": f"Bearer {build_access_token()}"},
                query_string="status=AVAILABLE",
            ),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    )
    get_response = asyncio.run(
        item_resource(
            item_id="item-1",
            request=build_request("/api/items/item-1", headers={"Authorization": f"Bearer {build_access_token()}"}),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    )
    patch_response = asyncio.run(
        item_status_resource(
            item_id="item-1",
            request=build_request(
                "/api/items/item-1/status",
                method="PATCH",
                headers={"Authorization": f"Bearer {build_access_token()}"},
                json_body={"status": "MATCHED", "reason": "Teste"},
            ),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    )
    history_response = asyncio.run(
        item_history_resource(
            item_id="item-1",
            request=build_request(
                "/api/items/item-1/history",
                headers={"Authorization": f"Bearer {build_access_token()}"},
            ),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    )

    assert list_response.status_code == 200
    assert get_response.status_code == 200
    assert patch_response.status_code == 200
    assert history_response.status_code == 200
    assert fake_proxy_service.calls[0]["query_params"]["status"] == "AVAILABLE"


def test_match_routes_are_forwarded(fake_proxy_service) -> None:
    fake_proxy_service.responses[("matching", "GET", "/matches")] = JSONResponse(status_code=200, content=[])
    fake_proxy_service.responses[("matching", "GET", "/matches/m-1")] = JSONResponse(status_code=200, content={"id": "m-1"})
    fake_proxy_service.responses[("matching", "POST", "/matches/m-1/accept")] = JSONResponse(
        status_code=200,
        content={"id": "m-1", "status": "ACCEPTED"},
    )
    fake_proxy_service.responses[("matching", "POST", "/matches/m-1/reject")] = JSONResponse(
        status_code=200,
        content={"id": "m-1", "status": "REJECTED"},
    )

    claims = build_claims()
    assert asyncio.run(
        matches_collection(
            request=build_request("/api/matches", headers={"Authorization": f"Bearer {build_access_token()}"}),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    ).status_code == 200
    assert asyncio.run(
        match_resource(
            match_id="m-1",
            request=build_request("/api/matches/m-1", headers={"Authorization": f"Bearer {build_access_token()}"}),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    ).status_code == 200
    assert asyncio.run(
        match_accept(
            match_id="m-1",
            request=build_request(
                "/api/matches/m-1/accept",
                method="POST",
                headers={"Authorization": f"Bearer {build_access_token()}"},
                json_body={"decided_by_user_id": "11111111-1111-1111-1111-111111111111"},
            ),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    ).status_code == 200
    assert asyncio.run(
        match_reject(
            match_id="m-1",
            request=build_request(
                "/api/matches/m-1/reject",
                method="POST",
                headers={"Authorization": f"Bearer {build_access_token()}"},
                json_body={"decided_by_user_id": "11111111-1111-1111-1111-111111111111"},
            ),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    ).status_code == 200


def test_recovery_routes_are_forwarded(fake_proxy_service) -> None:
    fake_proxy_service.responses[("recovery", "GET", "/recovery-cases")] = JSONResponse(status_code=200, content=[])
    fake_proxy_service.responses[("recovery", "GET", "/recovery-cases/c-1")] = JSONResponse(
        status_code=200,
        content={"id": "c-1"},
    )
    fake_proxy_service.responses[("recovery", "POST", "/recovery-cases/c-1/cancel")] = JSONResponse(
        status_code=200,
        content={"id": "c-1", "status": "CANCELLED"},
    )
    fake_proxy_service.responses[("recovery", "POST", "/recovery-cases/c-1/complete")] = JSONResponse(
        status_code=200,
        content={"id": "c-1", "status": "COMPLETED"},
    )

    claims = build_claims()
    assert asyncio.run(
        recovery_cases_collection(
            request=build_request("/api/recovery-cases", headers={"Authorization": f"Bearer {build_access_token()}"}),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    ).status_code == 200
    assert asyncio.run(
        recovery_case_resource(
            case_id="c-1",
            request=build_request("/api/recovery-cases/c-1", headers={"Authorization": f"Bearer {build_access_token()}"}),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    ).status_code == 200
    assert asyncio.run(
        recovery_case_cancel(
            case_id="c-1",
            request=build_request(
                "/api/recovery-cases/c-1/cancel",
                method="POST",
                headers={"Authorization": f"Bearer {build_access_token()}"},
                json_body={"reason": "cancelado"},
            ),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    ).status_code == 200
    assert asyncio.run(
        recovery_case_complete(
            case_id="c-1",
            request=build_request(
                "/api/recovery-cases/c-1/complete",
                method="POST",
                headers={"Authorization": f"Bearer {build_access_token()}"},
                json_body={"reason": "concluído"},
            ),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    ).status_code == 200


def test_correlation_and_auth_headers_are_propagated(fake_proxy_service) -> None:
    claims = build_claims()
    response = asyncio.run(
        items_collection(
            request=build_request(
                "/api/items",
                headers={
                    "Authorization": f"Bearer {build_access_token()}",
                    "X-Correlation-ID": "corr-integration-1",
                },
            ),
            _claims=claims,
            proxy_service=fake_proxy_service,
        ),
    )

    assert response.status_code == 200
    assert fake_proxy_service.calls[0]["headers"]["authorization"].startswith("Bearer ")
    assert fake_proxy_service.calls[0]["headers"]["x-correlation-id"] == "corr-integration-1"


def test_downstream_failure_handlers_are_consistent() -> None:
    unavailable_response = asyncio.run(
        downstream_unavailable_error_handler(None, Exception("item offline")),
    )
    timeout_response = asyncio.run(
        downstream_timeout_error_handler(None, Exception("matching timeout")),
    )

    assert unavailable_response.status_code == 502
    assert json.loads(unavailable_response.body)["detail"] == "item offline"
    assert timeout_response.status_code == 504
    assert json.loads(timeout_response.body)["detail"] == "matching timeout"
