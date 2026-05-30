import time
from uuid import uuid4

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.exceptions import GatewayAuthenticationError
from app.services.security import decode_access_token, extract_bearer_token


def test_extract_bearer_token_reads_authorization_header() -> None:
    assert extract_bearer_token("Bearer abc.def") == "abc.def"


def test_decode_access_token_validates_claims() -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "role": "USER",
            "exp": int(time.time()) + 3600,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    claims = decode_access_token(token)

    assert claims.role == "USER"
    assert claims.sub is not None
    assert claims.exp > int(time.time())


def test_decode_access_token_rejects_invalid_token() -> None:
    with pytest.raises(GatewayAuthenticationError, match="Token inválido ou expirado"):
        decode_access_token("invalid-token")


def test_decode_access_token_rejects_missing_claims() -> None:
    settings = get_settings()
    token = jwt.encode(
        {"sub": str(uuid4()), "exp": int(time.time()) + 3600},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(GatewayAuthenticationError, match="Claims obrigatórias ausentes"):
        decode_access_token(token)
