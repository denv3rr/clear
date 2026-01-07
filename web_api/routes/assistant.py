from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from web_api.auth import require_api_key
from web_api.summarizer import summarize

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
    else:
        response = {
            "answer": f"Mode '{payload.mode}' is not yet implemented.",
            "sources": [],
            "confidence": "Low",
            "warnings": ["This assistant mode is not yet available."],
        }

    return response
