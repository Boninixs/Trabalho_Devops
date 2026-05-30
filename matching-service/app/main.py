""""
Esse arquivo é responsável por configurar e iniciar o serviço de matching.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import RequestLoggingMiddleware, configure_logging, get_logger
from app.messaging.consumer import ItemEventsConsumer
from app.messaging.publisher import OutboxPublisher

settings = get_settings()
configure_logging(service_name=settings.service_name, log_level=settings.log_level)
logger = get_logger(__name__)
item_events_consumer = ItemEventsConsumer()
outbox_publisher = OutboxPublisher()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """"
    Gerenciador de contexto para o ciclo de vida do aplicativo, responsável por iniciar e parar os 
    componentes do serviço.
    args:
        _: A instância do FastAPI.
    returns:
        Um gerenciador de contexto assíncrono que inicia os componentes do serviço.  
    """
    logger.info("service_starting")
    if settings.outbox_publisher_enabled:
        await outbox_publisher.start()
    else:
        logger.info("outbox_publisher_disabled")
    if settings.event_consumer_enabled:
        await item_events_consumer.start()
    else:
        logger.info("item_events_consumer_disabled")
    yield
    await outbox_publisher.stop()
    await item_events_consumer.stop()
    logger.info("service_stopping")


app = FastAPI(
    title=settings.service_name,
    description="Matching service for LOST and FOUND item suggestions.",
    version=settings.service_version,
    lifespan=lifespan,
)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(api_router)
