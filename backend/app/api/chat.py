"""Chat endpoint: POST /api/chat."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.llm.service import handle_chat
from app.market import MarketDataSource, PriceCache

from .deps import get_cache, get_conn, get_source

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Body for POST /api/chat."""

    message: str


@router.post("")
async def post_chat(
    body: ChatRequest,
    conn: aiosqlite.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
    source: MarketDataSource = Depends(get_source),
) -> dict:
    """Send a message to the FinAlly assistant and auto-execute its actions."""
    return await handle_chat(conn, cache, source, body.message)
