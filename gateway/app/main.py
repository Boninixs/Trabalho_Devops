from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    DownstreamServiceTimeoutError,
    DownstreamServiceUnavailableError,
    GatewayAuthenticationError,
    GatewayAuthorizationError,
    InternalRouteBlockedError,
)
from app.core.logging import RequestLoggingMiddleware, configure_logging, get_logger

settings = get_settings()
configure_logging(service_name=settings.service_name, log_level=settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("service_starting")
    yield
    logger.info("service_stopping")


app = FastAPI(
    title=settings.service_name,
    description="HTTP-only API Gateway for routing, JWT validation and simple access control.",
    version=settings.service_version,
    lifespan=lifespan,
)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(api_router)


@app.exception_handler(GatewayAuthenticationError)
async def gateway_authentication_error_handler(_, exc: GatewayAuthenticationError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(GatewayAuthorizationError)
async def gateway_authorization_error_handler(_, exc: GatewayAuthorizationError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(InternalRouteBlockedError)
async def internal_route_blocked_error_handler(_, exc: InternalRouteBlockedError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DownstreamServiceTimeoutError)
async def downstream_timeout_error_handler(_, exc: DownstreamServiceTimeoutError) -> JSONResponse:
    return JSONResponse(status_code=504, content={"detail": str(exc)})


@app.exception_handler(DownstreamServiceUnavailableError)
async def downstream_unavailable_error_handler(_, exc: DownstreamServiceUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})
