from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.db_management import create_db_and_tables
from modules.client_store import bootstrap_clients_from_json
from web_api.routes import build_router

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    bootstrap_clients_from_json()
    yield


app = FastAPI(title="Clear Web API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(build_router())

@app.options("/{path:path}")
async def options_handler(path: str):
    return {"message": "OK"}
