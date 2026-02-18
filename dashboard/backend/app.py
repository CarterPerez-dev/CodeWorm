"""
ⒸAngelaMos | 2026
dashboard/backend/app.py
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from dashboard.backend.api import router as api_router
from dashboard.backend.ws import (
    router as ws_router,
    start_redis_subscriber,
    stop_redis_subscriber,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await start_redis_subscriber()
    yield
    await stop_redis_subscriber()


app = FastAPI(
    title="CodeWorm Dashboard",
    version="1.0.2",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="")
app.include_router(ws_router, prefix="")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "healthy"})


static_dir = Path(__file__).parent.parent / "frontend" / "dist"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
