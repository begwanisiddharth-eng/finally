"""Health check endpoint."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends

from .deps import get_conn

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(conn: aiosqlite.Connection = Depends(get_conn)) -> dict:
    """Liveness check: confirms the DB connection responds to SELECT 1."""
    await conn.execute("SELECT 1")
    return {"ok": True}
