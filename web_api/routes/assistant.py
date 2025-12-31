from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from web_api.auth import require_api_key
from web_api.context import build_context
from web_api.summarizer import summarize

router = APIRouter()


@router.post("/api/assistant/query")
def query(
    request: Request,
    question: str,
    context: dict | None = None,
    sources: list[str] | None = None,
    mode: str = "summary",
    api_key: str = Depends(require_api_key),
):
    context_str = build_context(context)
    
    if mode == "summary":
        answer = summarize(request, question, context_str, sources)
    else:
        answer = f"Mode '{mode}' is not yet implemented."

    return {
        "answer": answer,
        "sources": [],
        "confidence": "Low",
        "warnings": ["This is a placeholder response."],
    }
