from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.recovery_cases import router as recovery_cases_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(recovery_cases_router)
