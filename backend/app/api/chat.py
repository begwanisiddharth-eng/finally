"""Chat endpoint: POST /api/chat."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db import list_recent_chat_messages
from app.llm.service import handle_chat
from app.market import MarketDataSource, PriceCache

from .deps import get_cache, get_conn, get_source

router = APIRouter(prefix="/api/chat", tags=["chat"])

HISTORY_LIMIT = 50


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


@router.get("/history")
async def get_chat_history(
    conn: aiosqlite.Connection = Depends(get_conn),
) -> list[dict]:
    """Recent chat messages (oldest-first) so the UI can rehydrate on load.

    Each message is {role, content, actions}; actions carries the executed
    trade/watchlist results for assistant turns, or null for user turns.
    """
    return await list_recent_chat_messages(conn, limit=HISTORY_LIMIT)
