"""
Esse arquivo é responsável pelas dependências de autenticação e autorização.
"""
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user_repository import get_user_by_id
from app.schemas.user import TokenClaims

security = HTTPBearer(auto_error=False)


def get_current_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> TokenClaims:
    """
    Extrai e valida os claims do token JWT.
    Args:
        credentials: Credenciais HTTP contendo o token Bearer.
    Returns:
        Claims decodificados do token.
    Raises:
        HTTPException: Caso o token não seja fornecido ou seja inválido.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais não fornecidas",
        )

    try:
        return decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def get_current_user(
    claims: TokenClaims = Depends(get_current_token_claims),
    db: Session = Depends(get_db),
) -> User:
    """
    Recupera o usuário a partir do token.
    Args:
        claims: Dados extraídos do token JWT.
        db: Sessão do banco de dados.
    Returns:
        Usuário correspondente ao token.
    Raises:
        HTTPException: Caso o usuário não seja encontrado.
    """
    user = get_user_by_id(db, claims.subject)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário do token não encontrado",
        )

    return user


def get_current_active_user(
        current_user: User = Depends(get_current_user),
) -> User:
    """
    Garante que o usuário está ativo.
    Args:
        current_user: Usuário autenticado.
    Returns:
        Usuário ativo.
    Raises:
        HTTPException: Caso o usuário esteja inativo.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo",
        )

    return current_user


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """
    Cria uma dependência que valida os papéis do usuário.
    Args:
        roles: Papéis permitidos para acesso.
    Returns:
        Função de dependência que valida o papel do usuário.
    Raises:
        HTTPException: Caso o usuário não tenha permissão.
    """
    allowed_roles = {role.value for role in roles}

    def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado para o perfil informado",
            )

        return current_user

    return dependency
