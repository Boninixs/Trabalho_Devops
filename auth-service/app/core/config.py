"""
Esse arquivo é responsável pela configuração central da aplicação.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_environment(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "development": "dev",
        "develop": "dev",
        "local": "dev",
        "dev": "dev",
        "homol": "homol",
        "homolog": "homol",
        "homologation": "homol",
        "staging": "homol",
        "hml": "homol",
        "production": "prod",
        "prod": "prod",
        "main": "prod",
    }
    return aliases.get(normalized, normalized)


class Settings(BaseSettings):
    """
    Classe de configurações da aplicação.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(
        default="auth-service", 
        alias="SERVICE_NAME",
    )
    service_version: str = Field(
        default="0.1.0", 
        alias="SERVICE_VERSION",
    )
    service_port: int = Field(
        default=8000, 
        alias="SERVICE_PORT",
        )
    environment: str = Field(
        default="development", 
        alias="ENVIRONMENT",
    )
    swagger_env: str = Field(
        default="DEV",
        alias="SWAGGER_ENV",
    )
    log_level: str = Field(
        default="INFO", 
        alias="LOG_LEVEL",
    )
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5433/auth_service",
        alias="DATABASE_URL",
    )
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    rabbitmq_url: str = Field(
        default="amqp://app:app@localhost:5672/",
        alias="RABBITMQ_URL",
    )
    rabbitmq_events_exchange: str = Field(
        default="domain.events",
        alias="RABBITMQ_EVENTS_EXCHANGE",
    )
    rabbitmq_dead_letter_exchange: str = Field(
        default="domain.events.dlx",
        alias="RABBITMQ_DEAD_LETTER_EXCHANGE",
    )
    jwt_secret: str = Field(
        default="change-me-in-phase-1", 
        alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(
        default="HS256", 
        alias="JWT_ALGORITHM",
    )
    access_token_expire_minutes: int = Field(
        default=60,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    def is_swagger_enabled(self) -> bool:
        """Retorna True quando o ambiente atual corresponde ao ambiente liberado para Swagger."""
        return _normalize_environment(self.environment) == _normalize_environment(self.swagger_env)


@lru_cache
def get_settings() -> Settings:
    """
    Retorna uma instância única de Settings.
    args:
        None
    Returns:
        Instância de Settings carregada.
    """
    return Settings()


settings = get_settings()
SECRET_KEY = settings.jwt_secret
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
