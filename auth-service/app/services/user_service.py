"""
Esse arquivo é responsável por fornecer a lógica de negócios relacionada aos usuários. 
"""
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, DuplicateEmailError, InactiveUserError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.user_repository import add_user, get_user_by_email
from app.schemas.user import LoginRequest, TokenResponse, UserRegisterRequest


def normalize_email(email: str) -> str:
    """
    Normaliza o email, removendo espaços em branco e convertendo para minúsculas.
    args:   
        email: O email a ser normalizado.
    returns:
        str: O email normalizado.
    """
    return email.strip().lower()


def register_user(session: Session, payload: UserRegisterRequest) -> User:
    """
    Registra um novo usuário, verificando se o email já está em uso.
    args:
        session: Sessão do banco de dados.
        payload: A solicitação de registro contendo nome completo, email e senha do usuário.
    returns:
        User: O usuário registrado.
    raises:
        DuplicateEmailError: Se o email já estiver em uso por outro usuário.
    """
    normalized_email = normalize_email(payload.email)
    existing_user = get_user_by_email(session, normalized_email)
    if existing_user is not None:
        raise DuplicateEmailError("Email já cadastrado")

    user = User(
        full_name=payload.full_name.strip(),
        email=normalized_email,
        password_hash=hash_password(payload.password),
        role=UserRole.USER,
        is_active=True,
    )
    add_user(session, user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(session: Session, payload: LoginRequest) -> TokenResponse:
    """
    Autentica um usuário com base em seu email e senha.
    args:
        session: Sessão do banco de dados.
        payload: A solicitação de login contendo email e senha.
    returns:
        TokenResponse: A resposta contendo o token de acesso e o tempo de expiração.
    raises:
        AuthenticationError: Se o email ou senha estiverem incorretos.
        InactiveUserError: Se o usuário estiver inativo.
    """
    normalized_email = normalize_email(payload.email)
    user = get_user_by_email(session, normalized_email)

    if user is None or not verify_password(payload.password, user.password_hash):
        raise AuthenticationError("Email ou senha inválidos")

    if not user.is_active:
        raise InactiveUserError("Usuário inativo")

    settings = get_settings()
    token = create_access_token(subject=user.id, role=user.role.value)
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
    )
