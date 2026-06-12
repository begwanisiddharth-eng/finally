"""Shared trade execution service.

Executes market orders at the current cached price. Used by both the
REST trade endpoint and the LLM chat auto-execution path, so the same
validation and bookkeeping run regardless of caller.
"""

from __future__ import annotations

import aiosqlite

from app.db import (
    MIN_QUANTITY,
    delete_position,
    get_cash_balance,
    get_position,
    insert_snapshot,
    insert_trade,
    set_cash_balance,
    upsert_position,
)
from app.market import PriceCache

from .portfolio import compute_total_value


class TradeError(Exception):
    """Raised when a trade cannot be executed (bad input / business rule)."""


async def execute_trade(
    conn: aiosqlite.Connection,
    cache: PriceCache,
    ticker: str,
    side: str,
    quantity: float,
) -> dict:
    """Execute a market order at the current price and persist the result.

    Buy: validates cash, decrements cash, upserts the position with a
    recomputed average cost. Sell: validates held quantity, increments cash,
    reduces or removes the position. Both append a trade row and write a
    portfolio snapshot.

    Returns the trade response dict. Raises TradeError on any validation
    failure (caller maps this to a 400 error envelope).
    """
    ticker = ticker.upper()
    if side not in ("buy", "sell"):
        raise TradeError(f"Invalid side: {side}")
    if quantity < MIN_QUANTITY:
        raise TradeError(f"Quantity must be at least {MIN_QUANTITY}")

    price = cache.get_price(ticker)
    if price is None:
        raise TradeError(f"No price available for {ticker}")

    if side == "buy":
        await _execute_buy(conn, ticker, quantity, price)
    else:
        await _execute_sell(conn, ticker, quantity, price)

    trade = await insert_trade(conn, ticker, side, quantity, price)
    total_value = await compute_total_value(conn, cache)
    await insert_snapshot(conn, total_value)

    cash_balance = await get_cash_balance(conn)
    return {
        "ok": True,
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": trade["executed_at"],
        "cash_balance": round(cash_balance, 2),
    }


async def _execute_buy(
    conn: aiosqlite.Connection, ticker: str, quantity: float, price: float
) -> None:
    cost = quantity * price
    cash = await get_cash_balance(conn)
    if cost > cash:
        raise TradeError("Insufficient cash")

    position = await get_position(conn, ticker)
    if position:
        old_qty = position["quantity"]
        old_cost = position["avg_cost"]
        new_qty = old_qty + quantity
        new_avg = (old_qty * old_cost + quantity * price) / new_qty
    else:
        new_qty = quantity
        new_avg = price

    await set_cash_balance(conn, cash - cost)
    await upsert_position(conn, ticker, new_qty, new_avg)


async def _execute_sell(
    conn: aiosqlite.Connection, ticker: str, quantity: float, price: float
) -> None:
    position = await get_position(conn, ticker)
    if not position or position["quantity"] < quantity:
        raise TradeError("Insufficient shares to sell")

    proceeds = quantity * price
    cash = await get_cash_balance(conn)
    remaining = position["quantity"] - quantity

    await set_cash_balance(conn, cash + proceeds)
    if remaining < MIN_QUANTITY:
        await delete_position(conn, ticker)
    else:
        await upsert_position(conn, ticker, remaining, position["avg_cost"])
