"""Shared watchlist mutation service.

Validates the ticker, updates the watchlist table, and starts/stops price
tracking on the market data source. Used by the REST watchlist routes and the
LLM chat auto-execution path so validation lives in one place.
"""

from __future__ import annotations

import re

import aiosqlite

from app.db import add_watchlist_ticker, remove_watchlist_ticker
from app.market import MarketDataSource

TICKER_RE = re.compile(r"^[A-Z0-9]{1,10}$")


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
