""""
Esse arquivo contém os testes unitários para as funções de segurança, como hashing de senha e criação/decodificação 
de tokens JWT.
"""
from uuid import UUID

import pytest

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.user import UserRole


def test_hash_password_generates_different_value_and_verifies() -> None:
    password = "senha123"

    hashed_password = hash_password(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password) is True


def test_decode_access_token_returns_required_claims() -> None:
    token = create_access_token(
        subject=UUID("6f8f0be4-1dcb-421c-9f2a-2db26d8bb089"),
        role=UserRole.ADMIN.value,
    )

    claims = decode_access_token(token)

    assert str(claims.subject) == "6f8f0be4-1dcb-421c-9f2a-2db26d8bb089"
    assert claims.role == UserRole.ADMIN
    assert claims.exp > 0


def test_decode_access_token_rejects_invalid_token() -> None:
    with pytest.raises(ValueError, match="Token inválido ou expirado"):
        decode_access_token("not-a-jwt")
