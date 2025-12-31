from __future__ import annotations

from fastapi import APIRouter

from web_api.view_model import attach_meta

router = APIRouter()


@router.get("/api/health")
def health_check():
    return attach_meta(
        {"status": "ok"},
        route="/api/health",
        source="system",
    )
