from fastapi import APIRouter, Depends, Request, Response

from app.core.exceptions import InternalRouteBlockedError
from app.schemas.auth import GatewayTokenClaims
from app.services.proxy_service import GatewayProxyService, get_proxy_service
from app.services.security import require_roles

router = APIRouter(prefix="/api", tags=["gateway"])


@router.api_route("/auth/register", methods=["POST"])
async def auth_register(
    request: Request,
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="auth", upstream_path="/auth/register")


@router.api_route("/auth/login", methods=["POST"])
async def auth_login(
    request: Request,
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="auth", upstream_path="/auth/login")


@router.api_route("/auth/me", methods=["GET"])
async def auth_me(
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="auth", upstream_path="/auth/me")


@router.api_route("/items", methods=["GET", "POST"])
async def items_collection(
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="item", upstream_path="/items")


@router.api_route("/items/{item_id}", methods=["GET", "PATCH"])
async def item_resource(
    item_id: str,
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="item", upstream_path=f"/items/{item_id}")


@router.api_route("/items/{item_id}/status", methods=["PATCH"])
async def item_status_resource(
    item_id: str,
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="item", upstream_path=f"/items/{item_id}/status")


@router.api_route("/items/{item_id}/history", methods=["GET"])
async def item_history_resource(
    item_id: str,
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="item", upstream_path=f"/items/{item_id}/history")


@router.api_route("/matches", methods=["GET"])
async def matches_collection(
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="matching", upstream_path="/matches")


@router.api_route("/matches/{match_id}", methods=["GET"])
async def match_resource(
    match_id: str,
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="matching", upstream_path=f"/matches/{match_id}")


@router.api_route("/matches/{match_id}/accept", methods=["POST"])
async def match_accept(
    match_id: str,
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="matching", upstream_path=f"/matches/{match_id}/accept")


@router.api_route("/matches/{match_id}/reject", methods=["POST"])
async def match_reject(
    match_id: str,
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="matching", upstream_path=f"/matches/{match_id}/reject")


@router.api_route("/recovery-cases", methods=["GET"])
async def recovery_cases_collection(
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="recovery", upstream_path="/recovery-cases")


@router.api_route("/recovery-cases/{case_id}", methods=["GET"])
async def recovery_case_resource(
    case_id: str,
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(request, service_name="recovery", upstream_path=f"/recovery-cases/{case_id}")


@router.api_route("/recovery-cases/{case_id}/cancel", methods=["POST"])
async def recovery_case_cancel(
    case_id: str,
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(
        request,
        service_name="recovery",
        upstream_path=f"/recovery-cases/{case_id}/cancel",
    )


@router.api_route("/recovery-cases/{case_id}/complete", methods=["POST"])
async def recovery_case_complete(
    case_id: str,
    request: Request,
    _claims: GatewayTokenClaims = Depends(require_roles("USER", "ADMIN")),
    proxy_service: GatewayProxyService = Depends(get_proxy_service),
) -> Response:
    return await proxy_service.forward(
        request,
        service_name="recovery",
        upstream_path=f"/recovery-cases/{case_id}/complete",
    )


@router.api_route("/internal/{internal_path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def block_internal_routes(internal_path: str) -> Response:
    raise InternalRouteBlockedError(f"Rota interna não exposta: /internal/{internal_path}")
