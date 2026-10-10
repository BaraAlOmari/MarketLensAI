from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db import check_database

router = APIRouter()


class DatabaseStatus(BaseModel):
    configured: bool
    ok: bool
    pgvector: str | None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str
    version: str
    database: DatabaseStatus


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Liveness. `status` is "ok" whenever the API is up; database details are informational."""
    settings = request.app.state.settings
    db = await check_database(request.app.state.db_pool)
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=request.app.version,
        database=DatabaseStatus(**db),
    )
