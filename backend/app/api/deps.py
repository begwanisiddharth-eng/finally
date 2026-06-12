"""FastAPI dependency providers.

The shared DB connection, price cache, and market data source are created at
startup and stored on app.state. These helpers expose them to route handlers.
"""

from __future__ import annotations

import aiosqlite
from fastapi import Request

from app.market import MarketDataSource, PriceCache


def get_conn(request: Request) -> aiosqlite.Connection:
    """The shared aiosqlite connection created at startup."""
    return request.app.state.conn


def get_cache(request: Request) -> PriceCache:
    """The shared price cache."""
    return request.app.state.cache


def get_source(request: Request) -> MarketDataSource:
    """The active market data source (simulator or Massive)."""
    return request.app.state.source
