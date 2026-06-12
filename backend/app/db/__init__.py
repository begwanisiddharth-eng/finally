"""Database layer for FinAlly.

Public API:
    connect              - Open a WAL-mode connection, lazily creating + seeding the DB
    db_path              - Absolute path to the SQLite file
    DEFAULT_USER         - The single user_id stub ("default")
    DEFAULT_CASH         - Seed cash balance (10000.0)
    SEED_TICKERS         - Default watchlist tickers
    MIN_QUANTITY         - Minimum tradeable share quantity (0.001)

    Cash:        get_cash_balance, set_cash_balance
    Watchlist:   list_watchlist, add_watchlist_ticker, remove_watchlist_ticker
    Positions:   get_position, list_positions, upsert_position, delete_position
    Trades:      insert_trade, list_trades
    Snapshots:   insert_snapshot, list_snapshots
    Chat:        insert_chat_message, list_recent_chat_messages
    Reset:       reset_portfolio
"""

from .connection import (
    DEFAULT_CASH,
    DEFAULT_USER,
    SEED_TICKERS,
    connect,
    db_path,
)
from .repository import (
    MIN_QUANTITY,
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

__all__ = [
    "connect",
    "db_path",
    "DEFAULT_USER",
    "DEFAULT_CASH",
    "SEED_TICKERS",
    "MIN_QUANTITY",
    "get_cash_balance",
    "set_cash_balance",
    "list_watchlist",
    "add_watchlist_ticker",
    "remove_watchlist_ticker",
    "get_position",
    "list_positions",
    "upsert_position",
    "delete_position",
    "insert_trade",
    "list_trades",
    "insert_snapshot",
    "list_snapshots",
    "insert_chat_message",
    "list_recent_chat_messages",
    "reset_portfolio",
]
