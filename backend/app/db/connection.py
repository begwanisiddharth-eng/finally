"""SQLite connection helper with lazy schema init and seeding."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import aiosqlite

# Project root is two levels up from this file: app/db/connection.py -> backend -> root.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "db" / "finally.db"
_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

DEFAULT_USER = "default"
DEFAULT_CASH = 10000.0
SEED_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]


def db_path() -> Path:
    """Absolute path to the SQLite database file.

    Defaults to project_root/db/finally.db, overridable via FINALLY_DB_PATH so
    tests / E2E can point at a throwaway database without touching the real one.
    """
    override = os.environ.get("FINALLY_DB_PATH", "").strip()
    return Path(override) if override else _DEFAULT_DB_PATH


async def connect(path: Path | None = None) -> aiosqlite.Connection:
    """Open a connection with WAL mode, ensuring schema and seed data exist.

    Idempotent: schema uses CREATE TABLE IF NOT EXISTS and seeding skips existing rows.
    Rows are returned as aiosqlite.Row (mapping access by column name).
    """
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(target)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await _init_schema(conn)
    await _seed(conn)
    return conn


async def _init_schema(conn: aiosqlite.Connection) -> None:
    """Create all tables if they do not already exist."""
    sql = _SCHEMA_PATH.read_text()
    await conn.executescript(sql)
    await conn.commit()


async def _seed(conn: aiosqlite.Connection) -> None:
    """Insert the default user and default watchlist if missing. Idempotent."""
    await conn.execute(
        "INSERT OR IGNORE INTO users_profile (user_id, cash_balance) VALUES (?, ?)",
        (DEFAULT_USER, DEFAULT_CASH),
    )
    for ticker in SEED_TICKERS:
        await conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker) VALUES (?, ?, ?)",
            (str(uuid.uuid4()), DEFAULT_USER, ticker),
        )
    await conn.commit()
