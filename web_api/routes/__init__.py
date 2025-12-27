from __future__ import annotations

from fastapi import APIRouter

from web_api.routes import clients, health, intel, reports, settings, tools, trackers, stream


def build_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    router.include_router(trackers.router)
    router.include_router(clients.router)
    router.include_router(reports.router)
    router.include_router(settings.router)
    router.include_router(tools.router)
    router.include_router(intel.router)
    router.include_router(stream.router)
    return router
