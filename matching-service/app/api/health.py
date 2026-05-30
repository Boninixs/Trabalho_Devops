"""
Esse arquivo é responsável pela rota de verificação de saúde da aplicação.
"""
from fastapi import APIRouter

from app.services.health_service import build_health_payload

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """
    Verifica o estado da aplicação.
    args:        
        None
    Returns:
        Dicionário contendo informações básicas de status do serviço.
    """
    return build_health_payload()

