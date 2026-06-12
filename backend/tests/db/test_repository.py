"""Tests for repository CRUD functions."""

import pytest

from app.db import (
    DEFAULT_CASH,
    add_watchlist_ticker,
    delete_position,
    get_cash_balance,
    get_position,
    insert_chat_message,
    insert_snapshot,
    insert_trade,
    list_positions,
    list_recent_chat_messages,
    list_snapshots,
    list_trades,
    list_watchlist,
    remove_watchlist_ticker,
    reset_portfolio,
    set_cash_balance,
    upsert_position,
)

# --- Cash ---


async def test_get_cash_balance_default(conn):
    assert await get_cash_balance(conn) == DEFAULT_CASH


async def test_set_cash_balance(conn):
    await set_cash_balance(conn, 8500.0)
    assert await get_cash_balance(conn) == 8500.0


# --- Watchlist ---


async def test_list_watchlist_seeded(conn):
    tickers = await list_watchlist(conn)
    assert "AAPL" in tickers and len(tickers) == 10


async def test_add_watchlist_ticker(conn):
    assert await add_watchlist_ticker(conn, "PYPL") is True
    assert "PYPL" in await list_watchlist(conn)


async def test_add_duplicate_ticker_returns_false(conn):
    assert await add_watchlist_ticker(conn, "AAPL") is False


async def test_remove_watchlist_ticker(conn):
    assert await remove_watchlist_ticker(conn, "AAPL") is True
    assert "AAPL" not in await list_watchlist(conn)


async def test_remove_missing_ticker_returns_false(conn):
    assert await remove_watchlist_ticker(conn, "ZZZZ") is False


async def test_watchlist_unique_constraint(conn):
    """Adding the same ticker twice never creates a second row."""
    await add_watchlist_ticker(conn, "PYPL")
    await add_watchlist_ticker(conn, "PYPL")
    cursor = await conn.execute("SELECT COUNT(*) AS n FROM watchlist WHERE ticker = 'PYPL'")
    assert (await cursor.fetchone())["n"] == 1


# --- Positions ---


async def test_get_position_none_initially(conn):
    assert await get_position(conn, "AAPL") is None


async def test_upsert_and_get_position(conn):
    await upsert_position(conn, "AAPL", 10.0, 190.0)
    pos = await get_position(conn, "AAPL")
    assert pos == {"ticker": "AAPL", "quantity": 10.0, "avg_cost": 190.0}


async def test_upsert_updates_existing(conn):
    await upsert_position(conn, "AAPL", 10.0, 190.0)
    await upsert_position(conn, "AAPL", 15.0, 192.0)
    pos = await get_position(conn, "AAPL")
    assert pos["quantity"] == 15.0 and pos["avg_cost"] == 192.0
    # Upsert must not create a duplicate row.
    cursor = await conn.execute("SELECT COUNT(*) AS n FROM positions WHERE ticker = 'AAPL'")
    assert (await cursor.fetchone())["n"] == 1


async def test_list_positions(conn):
    await upsert_position(conn, "AAPL", 10.0, 190.0)
    await upsert_position(conn, "MSFT", 5.0, 400.0)
    positions = await list_positions(conn)
    assert {p["ticker"] for p in positions} == {"AAPL", "MSFT"}


async def test_delete_position(conn):
    await upsert_position(conn, "AAPL", 10.0, 190.0)
    await delete_position(conn, "AAPL")
    assert await get_position(conn, "AAPL") is None


async def test_fractional_position(conn):
    await upsert_position(conn, "AAPL", 0.001, 190.0)
    pos = await get_position(conn, "AAPL")
    assert pos["quantity"] == 0.001


# --- Trades ---


async def test_insert_trade_returns_row(conn):
    trade = await insert_trade(conn, "AAPL", "buy", 10.0, 195.5)
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 10.0
    assert trade["price"] == 195.5
    assert trade["executed_at"]


async def test_list_trades_newest_first(conn):
    await insert_trade(conn, "AAPL", "buy", 10.0, 195.5)
    await insert_trade(conn, "MSFT", "sell", 5.0, 400.0)
    trades = await list_trades(conn)
    assert len(trades) == 2
    assert trades[0]["ticker"] == "MSFT"


# --- Snapshots ---


async def test_insert_and_list_snapshots(conn):
    await insert_snapshot(conn, 10000.0)
    await insert_snapshot(conn, 10250.0)
    snaps = await list_snapshots(conn)
    assert [s["total_value"] for s in snaps] == [10000.0, 10250.0]


# --- Chat ---


async def test_insert_chat_message_with_actions(conn):
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]}
    await insert_chat_message(conn, "assistant", "Bought AAPL", actions)
    messages = await list_recent_chat_messages(conn)
    assert messages[0]["actions"] == actions


async def test_insert_chat_message_null_actions(conn):
    await insert_chat_message(conn, "user", "hello")
    messages = await list_recent_chat_messages(conn)
    assert messages[0]["actions"] is None


async def test_list_recent_chat_oldest_first_and_limit(conn):
    for i in range(5):
        await insert_chat_message(conn, "user", f"msg{i}")
    messages = await list_recent_chat_messages(conn, limit=3)
    # Last 3 messages, in chronological order.
    assert [m["content"] for m in messages] == ["msg2", "msg3", "msg4"]


# --- Reset ---


async def test_reset_portfolio(conn):
    await set_cash_balance(conn, 5000.0)
    await upsert_position(conn, "AAPL", 10.0, 190.0)
    await insert_trade(conn, "AAPL", "buy", 10.0, 190.0)
    await insert_snapshot(conn, 7000.0)
    await insert_chat_message(conn, "user", "keep me")

    await reset_portfolio(conn)

    assert await get_cash_balance(conn) == DEFAULT_CASH
    assert await list_positions(conn) == []
    assert await list_trades(conn) == []
    assert await list_snapshots(conn) == []
    # Watchlist and chat preserved.
    assert len(await list_watchlist(conn)) == 10
    assert len(await list_recent_chat_messages(conn)) == 1


@pytest.mark.parametrize("side", ["buy", "sell"])
async def test_trade_sides(conn, side):
    trade = await insert_trade(conn, "AAPL", side, 1.0, 100.0)
    assert trade["side"] == side
