from __future__ import annotations

from fastapi import APIRouter, Depends

from web_api.view_model import attach_meta
from web_api.auth import require_api_key

router = APIRouter()


@router.get("/api/health")
def health_check(_auth: None = Depends(require_api_key)):
    return attach_meta(
        {"status": "ok"},
        route="/api/health",
        source="system",
    )
