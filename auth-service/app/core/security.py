"""
Esse arquivo é responsável pelos utilitários de segurança para autenticação.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.schemas.user import TokenClaims

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Gera o hash de uma senha.
    Args:
        password: Senha em texto plano.
    Returns:
        Senha criptografada.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se uma senha em texto plano corresponde ao hash fornecido.
    Args:
        plain_password: Senha em texto plano.
        hashed_password: Hash da senha.
    Returns:
        True se a senha estiver correta, False se não.
    """
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(*, subject: UUID, role: str) -> str:
    """
    Cria um token JWT de acesso.
    Args:
        subject: Identificador do usuário (UUID).
        role: Papel do usuário.
    Returns:
        Token JWT assinado.
    """
    settings = get_settings()
    expire_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes,
    )
    claims = {
        "sub": str(subject),
        "role": role,
        "exp": expire_at,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenClaims:
    """
    Decodifica e valida um token JWT.
    Args:
        token: Token JWT.
    Returns:
        Claims validados do token.
    Raises:
        ValueError: Caso o token seja inválido, expirado ou incompleto.
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Token inválido ou expirado") from exc

    try:
        return TokenClaims.model_validate(payload)
    except Exception as exc:
        raise ValueError("Claims obrigatórias ausentes no token") from exc
