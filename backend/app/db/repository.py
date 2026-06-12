"""Async repository functions for FinAlly persistence.

All functions take an open aiosqlite.Connection as their first argument and
operate on the default user. They commit their own writes.
"""

from __future__ import annotations

import json
import uuid

import aiosqlite

from .connection import DEFAULT_CASH, DEFAULT_USER

MIN_QUANTITY = 0.001


def _new_id() -> str:
    return str(uuid.uuid4())


# --- Cash balance --------------------------------------------------------


async def get_cash_balance(conn: aiosqlite.Connection, user_id: str = DEFAULT_USER) -> float:
    """Return the user's cash balance."""
    cursor = await conn.execute(
        "SELECT cash_balance FROM users_profile WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    return row["cash_balance"]


async def set_cash_balance(
    conn: aiosqlite.Connection, balance: float, user_id: str = DEFAULT_USER
) -> None:
    """Set the user's cash balance to an absolute value."""
    await conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE user_id = ?", (balance, user_id)
    )
    await conn.commit()


# --- Watchlist -----------------------------------------------------------


async def list_watchlist(
    conn: aiosqlite.Connection, user_id: str = DEFAULT_USER
) -> list[str]:
    """Return watchlist tickers ordered by when they were added."""
    cursor = await conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at, ticker",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [row["ticker"] for row in rows]


async def add_watchlist_ticker(
    conn: aiosqlite.Connection, ticker: str, user_id: str = DEFAULT_USER
) -> bool:
    """Add a ticker to the watchlist. Returns False if it was already present."""
    cursor = await conn.execute(
        "INSERT OR IGNORE INTO watchlist (id, user_id, ticker) VALUES (?, ?, ?)",
        (_new_id(), user_id, ticker),
    )
    await conn.commit()
    return cursor.rowcount > 0


async def remove_watchlist_ticker(
    conn: aiosqlite.Connection, ticker: str, user_id: str = DEFAULT_USER
) -> bool:
    """Remove a ticker from the watchlist. Returns False if it was not present."""
    cursor = await conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
    )
    await conn.commit()
    return cursor.rowcount > 0


# --- Positions -----------------------------------------------------------


async def get_position(
    conn: aiosqlite.Connection, ticker: str, user_id: str = DEFAULT_USER
) -> dict | None:
    """Return a single position as a dict, or None if the user holds no shares."""
    cursor = await conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_positions(
    conn: aiosqlite.Connection, user_id: str = DEFAULT_USER
) -> list[dict]:
    """Return all positions as a list of dicts (ticker, quantity, avg_cost)."""
    cursor = await conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? ORDER BY ticker",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def upsert_position(
    conn: aiosqlite.Connection,
    ticker: str,
    quantity: float,
    avg_cost: float,
    user_id: str = DEFAULT_USER,
) -> None:
    """Insert or update a position with the given quantity and average cost."""
    await conn.execute(
        """
        INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT (user_id, ticker)
        DO UPDATE SET quantity = excluded.quantity,
                      avg_cost = excluded.avg_cost,
                      updated_at = datetime('now')
        """,
        (_new_id(), user_id, ticker, quantity, avg_cost),
    )
    await conn.commit()


async def delete_position(
    conn: aiosqlite.Connection, ticker: str, user_id: str = DEFAULT_USER
) -> None:
    """Remove a position entirely (e.g., when quantity reaches zero)."""
    await conn.execute(
        "DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
    )
    await conn.commit()


# --- Trades --------------------------------------------------------------


async def insert_trade(
    conn: aiosqlite.Connection,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER,
) -> dict:
    """Append a trade to the ledger. Returns the stored row including executed_at."""
    trade_id = _new_id()
    await conn.execute(
        """
        INSERT INTO trades (id, user_id, ticker, side, quantity, price)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, user_id, ticker, side, quantity, price),
    )
    await conn.commit()
    cursor = await conn.execute(
        "SELECT ticker, side, quantity, price, executed_at FROM trades WHERE id = ?",
        (trade_id,),
    )
    row = await cursor.fetchone()
    return dict(row)


async def list_trades(
    conn: aiosqlite.Connection, user_id: str = DEFAULT_USER
) -> list[dict]:
    """Return all trades newest-first."""
    cursor = await conn.execute(
        """
        SELECT ticker, side, quantity, price, executed_at
        FROM trades WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC
        """,
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# --- Portfolio snapshots -------------------------------------------------


async def insert_snapshot(
    conn: aiosqlite.Connection, total_value: float, user_id: str = DEFAULT_USER
) -> None:
    """Record a portfolio total-value snapshot."""
    await conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value) VALUES (?, ?, ?)",
        (_new_id(), user_id, total_value),
    )
    await conn.commit()


async def list_snapshots(
    conn: aiosqlite.Connection, user_id: str = DEFAULT_USER
) -> list[dict]:
    """Return all snapshots oldest-first (recorded_at, total_value)."""
    cursor = await conn.execute(
        """
        SELECT recorded_at, total_value
        FROM portfolio_snapshots WHERE user_id = ? ORDER BY recorded_at, rowid
        """,
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# --- Chat messages -------------------------------------------------------


async def insert_chat_message(
    conn: aiosqlite.Connection,
    role: str,
    content: str,
    actions: dict | list | None = None,
    user_id: str = DEFAULT_USER,
) -> None:
    """Store a chat message. actions is serialized to JSON or stored as NULL."""
    actions_json = json.dumps(actions) if actions is not None else None
    await conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions) VALUES (?, ?, ?, ?, ?)",
        (_new_id(), user_id, role, content, actions_json),
    )
    await conn.commit()


async def list_recent_chat_messages(
    conn: aiosqlite.Connection, limit: int = 20, user_id: str = DEFAULT_USER
) -> list[dict]:
    """Return the last N chat messages in chronological (oldest-first) order.

    actions is deserialized back to a dict/list, or None.
    """
    cursor = await conn.execute(
        """
        SELECT role, content, actions, created_at FROM chat_messages
        WHERE user_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?
        """,
        (user_id, limit),
    )
    rows = await cursor.fetchall()
    messages = []
    for row in reversed(rows):
        message = dict(row)
        message["actions"] = json.loads(message["actions"]) if message["actions"] else None
        messages.append(message)
    return messages


# --- Reset ---------------------------------------------------------------


async def reset_portfolio(conn: aiosqlite.Connection, user_id: str = DEFAULT_USER) -> None:
    """Restore cash to the default, clearing positions, trades, and snapshots.

    Watchlist and chat history are preserved (per spec).
    """
    await conn.execute("DELETE FROM positions WHERE user_id = ?", (user_id,))
    await conn.execute("DELETE FROM trades WHERE user_id = ?", (user_id,))
    await conn.execute("DELETE FROM portfolio_snapshots WHERE user_id = ?", (user_id,))
    await conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE user_id = ?", (DEFAULT_CASH, user_id)
    )
    await conn.commit()
