"""Versioned API router (``/api/v1``).

New feature routers are registered here in their phase. Keep versions stable:
breaking changes go to ``/api/v2``.
"""

from fastapi import APIRouter

from . import admin_reference, auth, farmer, forecast, health, market, reference

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(reference.router)
api_router.include_router(farmer.router)
api_router.include_router(admin_reference.router)
api_router.include_router(market.router)
api_router.include_router(forecast.router)
