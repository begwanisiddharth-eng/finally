"""Fixtures for API tests: temp DB, seeded price cache, fake market source."""

from __future__ import annotations

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import health, portfolio, watchlist
from app.db import connect
from app.main import _register_error_handlers
from app.market import PriceCache

SEED_PRICES = {
    "AAPL": 190.0,
    "GOOGL": 140.0,
    "MSFT": 420.0,
    "TSLA": 250.0,
}


class FakeSource:
    """Records add/remove calls; updates the cache like the real source."""

    def __init__(self, cache: PriceCache) -> None:
        self._cache = cache
        self.added: list[str] = []
        self.removed: list[str] = []

    async def add_ticker(self, ticker: str) -> None:
        self.added.append(ticker)
        self._cache.update(ticker, 100.0)

    async def remove_ticker(self, ticker: str) -> None:
        self.removed.append(ticker)
        self._cache.remove(ticker)


@pytest_asyncio.fixture
async def app(tmp_path):
    """A FinAlly app wired to a temp DB and a pre-seeded fake cache/source."""
    conn = await connect(tmp_path / "test.db")

    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        cache.update(ticker, price)

    application = FastAPI(title="FinAlly-test")
    _register_error_handlers(application)
    application.include_router(health.router)
    application.include_router(portfolio.router)
    application.include_router(watchlist.router)

    application.state.conn = conn
    application.state.cache = cache
    application.state.source = FakeSource(cache)

    yield application
    await conn.close()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
