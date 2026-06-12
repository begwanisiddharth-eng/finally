"""Watchlist endpoints: list, add, remove."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends

from app.db import list_watchlist
from app.market import MarketDataSource, PriceCache
from app.services.watchlist import WatchlistError, execute_watchlist_change

from .deps import get_cache, get_conn, get_source
from .errors import ApiError
from .schemas import WatchlistAddRequest

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
async def get_watchlist(
    conn: aiosqlite.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
) -> list[dict]:
    """Watchlist tickers with their latest cached price data.

    change_pct is the session change: current price vs session_open.
    """
    result = []
    for ticker in await list_watchlist(conn):
        update = cache.get(ticker)
        session_open = cache.get_session_open(ticker)
        price = update.price if update else None
        prev_price = update.previous_price if update else None
        change_pct = 0.0
        if price is not None and session_open:
            change_pct = round((price - session_open) / session_open * 100, 2)
        result.append(
            {
                "ticker": ticker,
                "price": price,
                "prev_price": prev_price,
                "session_open": session_open,
                "change_pct": change_pct,
            }
        )
    return result


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
