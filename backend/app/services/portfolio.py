"""Portfolio valuation helpers shared across endpoints and background tasks."""

from __future__ import annotations

import aiosqlite

from app.db import get_cash_balance, list_positions
from app.market import PriceCache

from .locks import db_write_lock


async def build_portfolio(conn: aiosqlite.Connection, cache: PriceCache) -> dict:
    """Return the full portfolio view: cash, positions with P&L, total value.

    Acquires db_write_lock so reads are consistent with concurrent trades.
    Positions are valued at the current cached price. Tickers with no cached
    price fall back to avg_cost so the holding still appears with zero P&L.
    """
    async with db_write_lock:
        return await _snapshot(conn, cache)


async def _snapshot(conn: aiosqlite.Connection, cache: PriceCache) -> dict:
    cash = await get_cash_balance(conn)
    positions = []
    holdings_value = 0.0

    for pos in await list_positions(conn):
        ticker = pos["ticker"]
        quantity = pos["quantity"]
        avg_cost = pos["avg_cost"]
        cached_price = cache.get_price(ticker)
        current_price = cached_price if cached_price is not None else avg_cost
        market_value = quantity * current_price
        cost_basis = quantity * avg_cost
        unrealized_pnl = market_value - cost_basis
        pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis else 0.0
        holdings_value += market_value

        positions.append(
            {
                "ticker": ticker,
                "quantity": quantity,
                "avg_cost": round(avg_cost, 2),
                "current_price": round(current_price, 2),
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            }
        )

    return {
        "cash_balance": round(cash, 2),
        "total_value": round(cash + holdings_value, 2),
        "positions": positions,
    }


async def compute_total_value(conn: aiosqlite.Connection, cache: PriceCache) -> float:
    """Total portfolio value. Caller must already hold db_write_lock."""
    cash = await get_cash_balance(conn)
    holdings = 0.0
    for pos in await list_positions(conn):
        price = cache.get_price(pos["ticker"])
        holdings += pos["quantity"] * (price if price is not None else pos["avg_cost"])
    return cash + holdings
