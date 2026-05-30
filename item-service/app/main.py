from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import RequestLoggingMiddleware, configure_logging, get_logger
from app.messaging.publisher import OutboxPublisher

settings = get_settings()
configure_logging(service_name=settings.service_name, log_level=settings.log_level)
logger = get_logger(__name__)
outbox_publisher = OutboxPublisher()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("service_starting")
    if settings.outbox_publisher_enabled:
        await outbox_publisher.start()
    else:
        logger.info("outbox_publisher_disabled")
    yield
    await outbox_publisher.stop()
    logger.info("service_stopping")


app = FastAPI(
    title=settings.service_name,
    description="Item lifecycle service and source of ItemCreated and ItemUpdated events.",
    version=settings.service_version,
    lifespan=lifespan,
)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(api_router)
