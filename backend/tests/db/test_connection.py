"""Tests for connection setup: schema creation, WAL mode, seeding idempotency."""

from app.db import DEFAULT_CASH, SEED_TICKERS, connect
from app.db.connection import DEFAULT_USER


async def test_schema_tables_created(conn):
    cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    rows = await cursor.fetchall()
    tables = {row["name"] for row in rows}
    expected = {
        "users_profile",
        "watchlist",
        "positions",
        "trades",
        "portfolio_snapshots",
        "chat_messages",
    }
    assert expected <= tables


async def test_wal_mode_enabled(conn):
    cursor = await conn.execute("PRAGMA journal_mode")
    row = await cursor.fetchone()
    assert row[0].lower() == "wal"


async def test_seed_default_user(conn):
    cursor = await conn.execute(
        "SELECT cash_balance FROM users_profile WHERE user_id = ?", (DEFAULT_USER,)
    )
    row = await cursor.fetchone()
    assert row["cash_balance"] == DEFAULT_CASH


async def test_seed_watchlist(conn):
    cursor = await conn.execute("SELECT ticker FROM watchlist")
    rows = await cursor.fetchall()
    assert {row["ticker"] for row in rows} == set(SEED_TICKERS)


async def test_seed_is_idempotent(tmp_path):
    path = tmp_path / "idem.db"
    c1 = await connect(path)
    await c1.close()
    # Reconnecting must not duplicate users or watchlist rows.
    c2 = await connect(path)
    user_cursor = await c2.execute("SELECT COUNT(*) AS n FROM users_profile")
    watch_cursor = await c2.execute("SELECT COUNT(*) AS n FROM watchlist")
    assert (await user_cursor.fetchone())["n"] == 1
    assert (await watch_cursor.fetchone())["n"] == len(SEED_TICKERS)
    await c2.close()
