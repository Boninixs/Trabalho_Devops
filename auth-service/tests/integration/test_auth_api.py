""""
Esse arquivo contém os testes de integração para a API de autenticação. 
Ele verifica se as rotas de registro, login e perfil do usuário.
"""
import pytest


pytestmark = pytest.mark.integration


def test_register_persists_user_in_postgres(integration_client) -> None:
    """"
    Este teste verifica se o endpoint de registro de usuário está funcionando corretamente. 
    """
    response = integration_client.post(
        "/auth/register",
        json={
            "full_name": "Aline Santos",
            "email": "aline@udesc.com",
            "password": "senha123",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "aline@udesc.com"
    assert payload["full_name"] == "Aline Santos"
    assert payload["role"] == "USER"
    assert payload["is_active"] is True


def test_login_returns_jwt_token(integration_client) -> None:
    """"
    Este teste verifica se o endpoint de login está funcionando corretamente.
    """
    integration_client.post(
        "/auth/register",
        json={
            "full_name": "Aline Santos",
            "email": "aline@udesc.com",
            "password": "senha123",
        },
    )

    response = integration_client.post(
        "/auth/login",
        json={
            "email": "aline@udesc.com",
            "password": "senha123",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] > 0


def test_me_returns_authenticated_profile(integration_client) -> None:
    """"
    Este teste verifica se o endpoint de perfil está funcionando corretamente.
    """
    integration_client.post(
        "/auth/register",
        json={
            "full_name": "Aline Santos",
            "email": "aline@udesc.com",
            "password": "senha123",
        },
    )
    login_response = integration_client.post(
        "/auth/login",
        json={
            "email": "aline@udesc.com",
            "password": "senha123",
        },
    )
    access_token = login_response.json()["access_token"]

    response = integration_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "aline@udesc.com"
    assert payload["full_name"] == "Aline Santos"


def test_me_rejects_invalid_token(integration_client) -> None:
    """"
    Este teste verifica se o endpoint de perfil rejeita tokens inválidos."""
    response = integration_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_me_rejects_missing_token(integration_client) -> None:
    """"
    Este teste verifica se o endpoint de perfil rejeita a ausência de token.
    """
    response = integration_client.get("/auth/me")

    assert response.status_code == 401
