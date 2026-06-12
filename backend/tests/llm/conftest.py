"""Fixtures for chat-flow tests: temp DB, seeded cache, fake market source."""

from __future__ import annotations

import pytest_asyncio

from app.db import connect
from app.market import PriceCache

SEED_PRICES = {"AAPL": 190.0, "NVDA": 500.0, "TSLA": 250.0}


class FakeSource:
    """Records add/remove calls; mutates the cache like the real source."""

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
async def conn(tmp_path):
    connection = await connect(tmp_path / "test.db")
    yield connection
    await connection.close()


@pytest_asyncio.fixture
def cache():
    c = PriceCache()
    for ticker, price in SEED_PRICES.items():
        c.update(ticker, price)
    return c


@pytest_asyncio.fixture
def source(cache):
    return FakeSource(cache)
