"""Shared watchlist mutation service.

Validates the ticker, updates the watchlist table, and starts/stops price
tracking on the market data source. Used by the REST watchlist routes and the
LLM chat auto-execution path so validation lives in one place.
"""

from __future__ import annotations

import re

import aiosqlite

from app.db import add_watchlist_ticker, list_watchlist, remove_watchlist_ticker
from app.market import MarketDataSource, PriceCache

TICKER_RE = re.compile(r"^[A-Z0-9]{1,10}$")


async def build_watchlist_view(conn: aiosqlite.Connection, cache: PriceCache) -> list[dict]:
    """Watchlist tickers with their latest cached price data.

    change_pct is the session change: current price vs session_open. Shared by
    the GET /api/watchlist route and the LLM chat context builder so the price
    shaping lives in one place.
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


class WatchlistError(Exception):
    """Raised when a watchlist change cannot be applied."""


async def execute_watchlist_change(
    conn: aiosqlite.Connection,
    source: MarketDataSource,
    ticker: str,
    action: str,
) -> dict:
    """Add or remove a ticker, syncing the market data source.

    Returns {ticker, action, ok: True}. Raises WatchlistError on bad input or
    when removing a ticker that is not present (callers map this to an error).
    """
    ticker = ticker.upper()
    if action not in ("add", "remove"):
        raise WatchlistError(f"Invalid watchlist action: {action}")
    if not TICKER_RE.match(ticker):
        raise WatchlistError("Ticker must be 1-10 uppercase alphanumeric characters")

    if action == "add":
        await add_watchlist_ticker(conn, ticker)
        await source.add_ticker(ticker)
    else:
        removed = await remove_watchlist_ticker(conn, ticker)
        if not removed:
            raise WatchlistError(f"{ticker} is not in the watchlist")
        await source.remove_ticker(ticker)

    return {"ticker": ticker, "action": action, "ok": True}
