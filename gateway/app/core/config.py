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
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="gateway", alias="SERVICE_NAME")
    service_version: str = Field(default="0.1.0", alias="SERVICE_VERSION")
    service_port: int = Field(default=8000, alias="SERVICE_PORT")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    swagger_env: str = Field(default="DEV", alias="SWAGGER_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    auth_service_base_url: str = Field(
        default="http://auth-service:8000",
        alias="AUTH_SERVICE_BASE_URL",
    )
    item_service_base_url: str = Field(
        default="http://item-service:8000",
        alias="ITEM_SERVICE_BASE_URL",
    )
    matching_service_base_url: str = Field(
        default="http://matching-service:8000",
        alias="MATCHING_SERVICE_BASE_URL",
    )
    recovery_case_service_base_url: str = Field(
        default="http://recovery-case-service:8000",
        alias="RECOVERY_CASE_SERVICE_BASE_URL",
    )
    downstream_timeout_seconds: float = Field(
        default=10.0,
        alias="DOWNSTREAM_TIMEOUT_SECONDS",
    )
    jwt_secret: str = Field(default="change-me-in-phase-1", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")

    def is_swagger_enabled(self) -> bool:
        """Retorna True quando o ambiente atual corresponde ao ambiente liberado para Swagger."""
        return _normalize_environment(self.environment) == _normalize_environment(self.swagger_env)


@lru_cache
def get_settings() -> Settings:
    return Settings()
