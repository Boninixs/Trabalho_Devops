""""
Esse arquivo contém os testes unitários para as funções de serviço relacionadas a usuários, 
como registro e autenticação.
"""
from uuid import uuid4

import pytest

from app.core.exceptions import AuthenticationError, DuplicateEmailError
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.services.user_service import authenticate_user, register_user
from app.schemas.user import LoginRequest, UserRegisterRequest


class DummySession:
    """"
    Esta classe é um mock simples para simular o comportamento de uma sessão de banco de dados 
    durante os testes unitários.
    """
    def __init__(self):
        """"
        O construtor inicializa as listas e flags para rastrear as operações realizadas na sessão.
        """
        self.added_objects = []
        self.committed = False
        self.refreshed = False

    def add(self, obj):
        """"
        O método add simula a adição de um objeto à sessão, armazenando-o em uma lista de verificação.
        """
        self.added_objects.append(obj)

    def commit(self):
        """"
        O método commit simula a confirmação das alterações na sessão, definindo uma flag para indicar que a operação foi realizada.
        """
        self.committed = True

    def refresh(self, _obj):
        """"
        O método refresh simula a atualização de um objeto na sessão, definindo uma flag para indicar que a operação foi realizada.
        """
        self.refreshed = True


def test_register_user_rejects_duplicate_email(monkeypatch) -> None:
    """
    Este teste verifica se a função de registro de usuário rejeita tentativas de registro com um email que já existe.
    """
    payload = UserRegisterRequest(
        full_name="Aline Santos",
        email="aline@udesc.com",
        password="senha123",
    )

    monkeypatch.setattr(
        "app.services.user_service.get_user_by_email",
        lambda _session, _email: User(
            id=uuid4(),
            full_name="Existing User",
            email="aline@udesc.com",
            password_hash="hashed",
            role=UserRole.USER,
            is_active=True,
        ),
    )

    with pytest.raises(DuplicateEmailError, match="Email já cadastrado"):
        register_user(DummySession(), payload)


def test_authenticate_user_returns_access_token(monkeypatch) -> None:
    """"
    Este teste verifica se a função de autenticação de usuário retorna um token de acesso válido quando as 
    credenciais corretas são fornecidas.
    """
    session = DummySession()
    user = User(
        id=uuid4(),
        full_name="Aline Santos",
        email="aline@udesc.com",
        password_hash=hash_password("senha123"),
        role=UserRole.USER,
        is_active=True,
    )

    monkeypatch.setattr(
        "app.services.user_service.get_user_by_email",
        lambda _session, _email: user,
    )

    response = authenticate_user(
        session,
        LoginRequest(email="aline@udesc.com", password="senha123"),
    )

    assert response.access_token
    assert response.token_type == "bearer"
    assert response.expires_in > 0


def test_authenticate_user_rejects_invalid_password(monkeypatch) -> None:
    """"
    Este teste verifica se a função de autenticação de usuário rejeita tentativas de login com senha incorreta.
    """
    session = DummySession()
    user = User(
        id=uuid4(),
        full_name="Jane Doe",
        email="jane@example.com",
        password_hash=hash_password("SuperSecret123"),
        role=UserRole.USER,
        is_active=True,
    )

    monkeypatch.setattr(
        "app.services.user_service.get_user_by_email",
        lambda _session, _email: user,
    )

    with pytest.raises(AuthenticationError, match="Email ou senha inválidos"):
        authenticate_user(
            session,
            LoginRequest(email="aline@udesc.com", password="WrongPassword123"),
        )
