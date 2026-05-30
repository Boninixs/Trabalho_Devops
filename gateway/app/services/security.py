from collections.abc import Callable

from fastapi import Depends, Request
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import GatewayAuthenticationError, GatewayAuthorizationError
from app.schemas.auth import GatewayTokenClaims


def extract_bearer_token(authorization_header: str | None) -> str:
    if not authorization_header:
        raise GatewayAuthenticationError("Token de acesso ausente")

    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise GatewayAuthenticationError("Cabeçalho Authorization inválido")
    return token


def decode_access_token(token: str) -> GatewayTokenClaims:
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise GatewayAuthenticationError("Token inválido ou expirado") from exc

    try:
        return GatewayTokenClaims.model_validate(payload)
    except Exception as exc:
        raise GatewayAuthenticationError("Claims obrigatórias ausentes no token") from exc


async def get_current_claims(request: Request) -> GatewayTokenClaims:
    token = extract_bearer_token(request.headers.get("Authorization"))
    return decode_access_token(token)


def require_roles(*allowed_roles: str) -> Callable:
    async def dependency(
        claims: GatewayTokenClaims = Depends(get_current_claims),
    ) -> GatewayTokenClaims:
        if allowed_roles and claims.role not in allowed_roles:
            raise GatewayAuthorizationError("Perfil sem acesso a esta rota")
        return claims

    return dependency
