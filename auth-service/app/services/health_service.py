""""
Esse arquivo é responsável por fornecer a lógica de negócios relacionada à saúde do serviço.
"""
from app.core.config import get_settings


def build_health_payload() -> dict[str, str]:
    """"
    Constrói o payload de saúde do serviço, contendo informações como status, nome do serviço, versão e ambiente.
    args:
        None
    returns:
        dict[str, str]: O payload de saúde do serviço.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.environment,
    }

