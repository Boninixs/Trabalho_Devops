"""
Esse arquivo é resposável pelas rotas de autenticação e gerenciamento de usuário.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.core.exceptions import (
    AuthenticationError,
    DuplicateEmailError,
    InactiveUserError,
)
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import LoginRequest, TokenResponse, UserProfileResponse, UserRegisterRequest
from app.services.user_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: UserRegisterRequest, 
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """
    Registra um novo usuário.
    Args:
        payload: Dados necessários para criação do usuário.
        db: Sessão do banco de dados.
    Returns:
        Dados do usuário criado.
    Raises:
        HTTPException: Caso o e-mail já esteja em uso.
    """
    try:
        user = register_user(db, payload)
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UserProfileResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, 
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Autentica um usuário.
    Args:
        payload: Credenciais de login (email e senha).
        db: Sessão do banco de dados.
    Returns:
        Token de autenticação.
    Raises:
        HTTPException: Caso as credenciais sejam inválidas
        ou o usuário esteja inativo.
    """
    try:
        return authenticate_user(db, payload)
    except (AuthenticationError, InactiveUserError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.get("/me", response_model=UserProfileResponse)
def get_me(
    current_user: User = Depends(
        require_roles(UserRole.USER, UserRole.ADMIN)
    ),
) -> UserProfileResponse:
    """
    Retorna os dados do usuário autenticado.
    Args:
        current_user: Usuário autenticado (injetado via dependência).
    Returns:
        Perfil do usuário atual.
    """
    return UserProfileResponse.model_validate(current_user)
