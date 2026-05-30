""""
Esse arquivo é o ponto de entrada da aplicação, onde a instância do FastAPI é criada, configurada e as rotas 
são incluídas. Ele também define o ciclo de vida da aplicação, registrando logs de início e parada do serviço.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import RequestLoggingMiddleware, configure_logging, get_logger

settings = get_settings()
configure_logging(service_name=settings.service_name, log_level=settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """"
    Define o ciclo de vida da aplicação, registrando logs de início e parada do serviço.
    args:
        _: FastAPI - A instância do FastAPI.
    returns:
        AsyncGenerator: Um gerador assíncrono que gerencia o ciclo de vida da aplicação.    
    """
    logger.info("service_starting")
    yield
    logger.info("service_stopping")


app = FastAPI(
    title=settings.service_name,
    description="Authentication and authorization service.",
    version=settings.service_version,
    lifespan=lifespan,
)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(api_router)
