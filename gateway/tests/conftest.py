import json
from pathlib import Path
import sys
import time
from uuid import uuid4

from jose import jwt
import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.config import get_settings
def build_access_token(*, role: str = "USER", exp_offset_seconds: int = 3600) -> str:
    settings = get_settings()
    now = int(time.time())
    return jwt.encode(
        {
            "sub": str(uuid4()),
            "role": role,
            "exp": now + exp_offset_seconds,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


class FakeProxyService:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.responses: dict[tuple[str, str, str], object] = {}

    async def forward(self, request, *, service_name: str, upstream_path: str):
        body = await request.body()
        call = {
            "service_name": service_name,
            "method": request.method,
            "upstream_path": upstream_path,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
            "body": body.decode("utf-8") if body else "",
        }
        self.calls.append(call)

        outcome = self.responses.get((service_name, request.method, upstream_path))
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is not None:
            return outcome

        return JSONResponse(
            status_code=200,
            content={
                "service_name": service_name,
                "method": request.method,
                "upstream_path": upstream_path,
            },
        )


@pytest.fixture
def fake_proxy_service() -> FakeProxyService:
    return FakeProxyService()


def build_request(
    path: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: dict | list | None = None,
    query_string: str = "",
) -> Request:
    request_headers = {key.lower(): value for key, value in (headers or {}).items()}
    body = b""
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        request_headers.setdefault("content-type", "application/json")

    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "method": method.upper(),
        "path": path,
        "headers": [(key.encode("utf-8"), value.encode("utf-8")) for key, value in request_headers.items()],
        "query_string": query_string.encode("utf-8"),
    }
    return Request(scope, receive)
