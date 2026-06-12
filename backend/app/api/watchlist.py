"""Watchlist endpoints: list, add, remove."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends

from app.market import MarketDataSource, PriceCache
from app.services.watchlist import (
    WatchlistError,
    build_watchlist_view,
    execute_watchlist_change,
)

from .deps import get_cache, get_conn, get_source
from .errors import ApiError
from .schemas import WatchlistAddRequest

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
async def get_watchlist(
    conn: aiosqlite.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
) -> list[dict]:
    """Watchlist tickers with their latest cached price data."""
    return await build_watchlist_view(conn, cache)


@router.post("")
async def post_watchlist(
    body: WatchlistAddRequest,
    conn: aiosqlite.Connection = Depends(get_conn),
    source: MarketDataSource = Depends(get_source),
) -> dict:
    """Add a ticker to the watchlist and start tracking its price."""
    try:
        result = await execute_watchlist_change(conn, source, body.ticker, "add")
    except WatchlistError as exc:
        raise ApiError(400, str(exc)) from exc
    return {"ok": True, "ticker": result["ticker"]}


@router.delete("/{ticker}")
async def delete_watchlist(
    ticker: str,
    conn: aiosqlite.Connection = Depends(get_conn),
    source: MarketDataSource = Depends(get_source),
) -> dict:
    """Remove a ticker from the watchlist and stop tracking it."""
    try:
        result = await execute_watchlist_change(conn, source, ticker, "remove")
    except WatchlistError as exc:
        # An absent ticker is a 404; malformed input is a 400.
        status = 404 if "not in the watchlist" in str(exc) else 400
        raise ApiError(status, str(exc)) from exc
    return {"ok": True, "ticker": result["ticker"]}
