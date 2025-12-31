from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web_api.routes import build_router

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


app = FastAPI(title="Clear Web API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(build_router())

@app.options("/{path:path}")
async def options_handler(path: str):
    return {"message": "OK"}

