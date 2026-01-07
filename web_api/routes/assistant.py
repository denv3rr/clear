from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from web_api.auth import require_api_key
from web_api.summarizer import summarize
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()


class AssistantQuery(BaseModel):
    question: str = Field(..., min_length=1)
    context: dict | None = None
    sources: list[str] | None = None
    mode: str = "summary"


@router.post("/api/assistant/query")
def query(
    payload: AssistantQuery,
    api_key: str = Depends(require_api_key),
):
    mode = payload.mode.lower().strip()

    if mode == "summary":
        response = summarize(payload.question, payload.context, payload.sources)
        warnings = validate_payload(
            response,
            required_keys=("answer", "sources", "confidence", "warnings"),
            warnings=response.get("warnings"),
        )
        return attach_meta(
            response,
            route="/api/assistant/query",
            source="assistant",
            warnings=warnings,
        )

    response = {
        "answer": f"Mode '{payload.mode}' is not yet implemented.",
        "sources": [],
        "confidence": "Low",
        "warnings": ["This assistant mode is not yet available."],
    }
    warnings = validate_payload(
        response,
        required_keys=("answer", "sources", "confidence", "warnings"),
        warnings=response.get("warnings"),
    )
    attach_meta(
        response,
        route="/api/assistant/query",
        source="assistant",
        warnings=warnings,
        status="error",
    )
    return JSONResponse(response, status_code=status.HTTP_501_NOT_IMPLEMENTED)
