"""Portfolio endpoints: view, trade, history, reset."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends

from app.db import list_snapshots, reset_portfolio
from app.market import PriceCache
from app.services.portfolio import build_portfolio
from app.services.trades import TradeError, execute_trade

from .deps import get_cache, get_conn
from .errors import ApiError
from .schemas import TradeRequest

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
async def get_portfolio(
    conn: aiosqlite.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
) -> dict:
    """Positions with current price and P&L, cash balance, and total value."""
    return await build_portfolio(conn, cache)


@router.post("/trade")
async def post_trade(
    body: TradeRequest,
    conn: aiosqlite.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
) -> dict:
    """Execute a market order at the current price."""
    try:
        return await execute_trade(conn, cache, body.ticker, body.side, body.quantity)
    except TradeError as exc:
        raise ApiError(400, str(exc)) from exc


@router.get("/history")
async def get_history(conn: aiosqlite.Connection = Depends(get_conn)) -> list[dict]:
    """Portfolio total-value snapshots over time (oldest-first)."""
    return await list_snapshots(conn)


@router.post("/reset")
async def post_reset(conn: aiosqlite.Connection = Depends(get_conn)) -> dict:
    """Reset to $10k cash, clearing positions, trades, and snapshots."""
    await reset_portfolio(conn)
    return {"ok": True}
