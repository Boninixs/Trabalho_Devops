from app.core.config import get_settings


def build_health_payload() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.environment,
        "mode": "http-only",
    }

