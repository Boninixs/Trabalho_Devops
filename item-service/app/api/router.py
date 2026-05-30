from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.internal_recovery import router as internal_recovery_router
from app.api.items import router as items_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(items_router)
api_router.include_router(internal_recovery_router)
