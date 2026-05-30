""""
Esse arquivo é responsável por definir a classe de configuração da aplicação.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """"
    Classe de configuração da aplicação, que carrega as variáveis de ambiente e fornece uma interface para acessar essas 
    configurações em toda a aplicação.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="matching-service", alias="SERVICE_NAME")
    service_version: str = Field(default="0.1.0", alias="SERVICE_VERSION")
    service_port: int = Field(default=8000, alias="SERVICE_PORT")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5435/matching_service",
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
    outbox_publisher_enabled: bool = Field(
        default=True,
        alias="OUTBOX_PUBLISHER_ENABLED",
    )
    outbox_publish_poll_interval_seconds: float = Field(
        default=1.0,
        alias="OUTBOX_PUBLISH_POLL_INTERVAL_SECONDS",
    )
    outbox_publish_batch_size: int = Field(
        default=50,
        alias="OUTBOX_PUBLISH_BATCH_SIZE",
    )
    outbox_publish_retry_delay_seconds: float = Field(
        default=2.0,
        alias="OUTBOX_PUBLISH_RETRY_DELAY_SECONDS",
    )
    outbox_publish_max_attempts: int = Field(
        default=10,
        alias="OUTBOX_PUBLISH_MAX_ATTEMPTS",
    )
    event_consumer_enabled: bool = Field(
        default=True,
        alias="EVENT_CONSUMER_ENABLED",
    )
    rabbitmq_item_events_queue: str = Field(
        default="matching-service.item-events",
        alias="RABBITMQ_ITEM_EVENTS_QUEUE",
    )


@lru_cache
def get_settings() -> Settings:
    """"
    Função para obter as configurações da aplicação.
    args:
        None
    returns:
        Settings: A instância da classe de configurações da aplicação, carregada com as variáveis de ambiente.
    """
    return Settings()
