"""
Esse arquivo é responsável por registrar e organizar todos os routers dos módulos da aplicação
"""
from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.matches import router as matches_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(matches_router)
