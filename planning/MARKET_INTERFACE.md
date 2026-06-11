# Market Data Interface Design

Unified Python interface for market data in FinAlly. Two implementations — a GBM simulator
(default, no API key needed) and the Massive REST API — behind one abstract base class.
All downstream code (SSE streaming, portfolio valuation, trade execution) is source-agnostic.

## Architecture

```
MarketDataSource (ABC)
├── SimulatorDataSource   ──→  GBMSimulator (500ms tick)
└── MassiveDataSource     ──→  Polygon.io REST poller (15s free / 2-5s paid)
            │
            ▼
       PriceCache  (thread-safe in-memory store)
            │
            ├──→  GET /api/stream/prices   (SSE, one event per ticker per 500ms)
            ├──→  GET /api/portfolio       (portfolio valuation)
            └──→  POST /api/portfolio/trade (trade execution — reads current price)
```

The data sources **push** into the cache on their own schedule. Consumers **pull** from it
on theirs. No direct coupling between producers and consumers.

---

## Core Data Model

```python
# backend/app/market/models.py

from dataclasses import dataclass, field
import time

@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        """Absolute price change from previous update."""
        return round(self.price - self.previous_price, 2)

    @property
    def change_percent(self) -> float:
        """Percentage change from previous update."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 2)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat'."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self, session_open: float | None = None) -> dict:
        """Serialize to the SSE/API wire format defined in PLAN.md §6 and §8."""
        from datetime import datetime, timezone
        ts = datetime.fromtimestamp(self.timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "ticker": self.ticker,
            "price": self.price,
            "prev_price": self.previous_price,     # wire name per spec
            "session_open": session_open if session_open is not None else self.price,
            "change_pct": self.change_percent,      # wire name per spec
            "direction": self.direction,
            "timestamp": ts,                        # ISO 8601
        }
```

`PriceUpdate` is the **only** type that leaves the market data layer. Frozen and slotted
for immutability and performance.

---

## Price Cache

Thread-safe in-memory store. One writer (the active data source); many readers.

```python
# backend/app/market/cache.py

import time
from threading import Lock
from .models import PriceUpdate


class PriceCache:
    """Thread-safe cache of the latest price per ticker.

    Key design properties:
    - One writer at a time (the active MarketDataSource background task)
    - Many concurrent readers (SSE generator, API handlers)
    - version counter for SSE change detection (no polling overhead)
    - session_open tracks the first price seen per ticker per process lifetime
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._session_open: dict[str, float] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically increasing; bumped on every update

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price. Returns the PriceUpdate created.

        First call for a ticker: previous_price == price (direction='flat').
        session_open is set on the first update and never overwritten.
        """
        with self._lock:
            ts = timestamp if timestamp is not None else time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            if ticker not in self._session_open:
                self._session_open[ticker] = round(price, 2)
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        """Latest PriceUpdate for a ticker, or None."""
        with self._lock:
            return self._prices.get(ticker)

    def get_price(self, ticker: str) -> float | None:
        """Convenience: just the price float, or None."""
        update = self.get(ticker)
        return update.price if update else None

    def get_all(self) -> dict[str, PriceUpdate]:
        """Shallow copy of all current prices."""
        with self._lock:
            return dict(self._prices)

    def get_session_open(self, ticker: str) -> float | None:
        """First price seen for this ticker this process lifetime, or None."""
        with self._lock:
            return self._session_open.get(ticker)

    def remove(self, ticker: str) -> None:
        """Remove a ticker (e.g., deleted from watchlist)."""
        with self._lock:
            self._prices.pop(ticker, None)
            self._session_open.pop(ticker, None)

    @property
    def version(self) -> int:
        """Monotonic counter. SSE generator polls this to detect changes."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

### Session Open

`session_open` is the price at the **first** observation per ticker per **process lifetime**
(not per calendar day). It resets when the backend restarts. Purpose: the frontend displays
"change since session start" which would otherwise require a `price_history` table.

---

## Abstract Interface

```python
# backend/app/market/interface.py

from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push price updates into a shared PriceCache on their own
    schedule. Downstream code never calls the data source directly for prices.

    Lifecycle:
        source = create_market_data_source(cache)
        await source.start(["AAPL", "GOOGL", ...])
        await source.add_ticker("TSLA")       # dynamic watchlist management
        await source.remove_ticker("GOOGL")
        await source.stop()                   # on app shutdown
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates. Must be called once before add/remove."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task. Safe to call multiple times."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker. No-op if already present. Takes effect on next cycle."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker. Also removes it from the PriceCache."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Current list of actively tracked tickers."""
```

---

## Massive Implementation

```python
# backend/app/market/massive_client.py

import asyncio
import logging
from massive import RESTClient
from massive.rest.models import SnapshotMarketType
from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)


class MassiveDataSource(MarketDataSource):
    """MarketDataSource backed by the Massive (Polygon.io) REST API.

    Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all watched
    tickers in a single API call per interval, then writes to PriceCache.

    Rate limits:
      Free tier:  5 req/min  → poll_interval=15.0s (default)
      Paid tiers: unlimited  → poll_interval=2.0–5.0s
    """

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: RESTClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = [t.upper().strip() for t in tickers]
        await self._poll_once()  # Immediate first poll — cache has data right away
        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        if not self._tickers or not self._client:
            return
        try:
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            for snap in snapshots:
                try:
                    self._cache.update(
                        ticker=snap.ticker,
                        price=snap.last_trade.price,
                        timestamp=snap.last_trade.timestamp / 1000.0,  # ms → seconds
                    )
                except (AttributeError, TypeError) as e:
                    logger.warning("Skipping snapshot for %s: %s", getattr(snap, "ticker", "?"), e)
        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            # Don't re-raise — loop retries on next interval

    def _fetch_snapshots(self) -> list:
        """Synchronous Massive API call. Runs in a thread pool."""
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

Key implementation points:
- `RESTClient` is **synchronous**; wrapped in `asyncio.to_thread()` to avoid blocking
- An **immediate first poll** in `start()` ensures the cache has data before the first SSE client connects
- `add_ticker` takes effect on the **next poll cycle** (new ticker appears within `poll_interval` seconds)
- Exceptions are caught at the loop level, not the individual snapshot level — a bad key or network
  failure is logged and retried without crashing

---

## Simulator Implementation

```python
# backend/app/market/simulator.py (key class)

import asyncio
from .cache import PriceCache
from .interface import MarketDataSource


class SimulatorDataSource(MarketDataSource):
    """MarketDataSource backed by the GBM simulator.

    Runs a background asyncio task that calls GBMSimulator.step() every
    `update_interval` seconds and writes results to PriceCache.
    """

    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,
        event_probability: float = 0.001,
    ) -> None:
        self._cache = price_cache
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._sim = GBMSimulator(tickers=tickers, ...)
        # Seed the cache immediately so SSE has data on first connect
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")

    async def _run_loop(self) -> None:
        while True:
            try:
                prices = self._sim.step()  # {ticker: new_price}
                for ticker, price in prices.items():
                    self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

See `MARKET_SIMULATOR.md` for `GBMSimulator` internals.

---

## Factory Function

```python
# backend/app/market/factory.py

import os
from .cache import PriceCache
from .interface import MarketDataSource


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Select the appropriate market data source based on environment.

    - MASSIVE_API_KEY set and non-empty  →  MassiveDataSource (real data, polls every 15s)
    - Otherwise                          →  SimulatorDataSource (GBM, updates every 500ms)

    Returns an unstarted source; caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        from .massive_client import MassiveDataSource
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        from .simulator import SimulatorDataSource
        return SimulatorDataSource(price_cache=price_cache)
```

---

## SSE Streaming Integration

```python
# backend/app/market/stream.py

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from .cache import PriceCache

logger = logging.getLogger(__name__)


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Factory: returns an APIRouter with the SSE endpoint wired to this cache."""
    router = APIRouter(prefix="/api/stream", tags=["streaming"])

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router


async def _generate_events(
    price_cache: PriceCache,
    request: Request,
    interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    """Yields SSE events: one JSON object per ticker per interval.

    Uses the cache version counter to detect updates without comparing
    individual prices. Stops cleanly when the client disconnects.
    """
    yield "retry: 1000\n\n"   # Tell the browser to reconnect after 1s if dropped

    last_version = -1
    while True:
        if await request.is_disconnected():
            break
        try:
            if price_cache.version != last_version:
                last_version = price_cache.version
                for ticker, update in price_cache.get_all().items():
                    session_open = price_cache.get_session_open(ticker)
                    yield f"data: {json.dumps(update.to_dict(session_open=session_open))}\n\n"
        except Exception:
            logger.exception("SSE stream error")
        await asyncio.sleep(interval)
```

**SSE event shape** (one per ticker per 500ms cadence):
```json
{
  "ticker": "AAPL",
  "price": 195.50,
  "prev_price": 194.20,
  "session_open": 190.00,
  "change_pct": 2.89,
  "direction": "up",
  "timestamp": "2026-01-01T10:00:00Z"
}
```

The version counter pattern means the SSE loop doesn't compare prices — it just checks
whether any update happened since last emission, then emits everything. This keeps the
hot path simple and allocation-free.

---

## Application Startup

```python
# Typical FastAPI lifespan wiring (backend/app/main.py)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.market import PriceCache, create_market_data_source, create_stream_router

DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    source = create_market_data_source(cache)
    await source.start(DEFAULT_TICKERS)

    app.state.price_cache = cache
    app.state.market_source = source

    yield  # App runs here

    await source.stop()

app = FastAPI(lifespan=lifespan)
app.include_router(create_stream_router(cache))
```

Watchlist add/remove during runtime:
```python
await app.state.market_source.add_ticker("PYPL")
await app.state.market_source.remove_ticker("NFLX")
# PriceCache is updated immediately for remove; new ticker appears on next cycle
```

---

## File Structure

```
backend/
  app/
    market/
      __init__.py          # Re-exports: PriceCache, PriceUpdate, MarketDataSource,
                           #             create_market_data_source, create_stream_router
      models.py            # PriceUpdate frozen dataclass
      interface.py         # MarketDataSource ABC
      cache.py             # PriceCache (thread-safe, version counter, session_open)
      factory.py           # create_market_data_source() — env-variable dispatch
      massive_client.py    # MassiveDataSource — Polygon.io REST poller
      simulator.py         # GBMSimulator + SimulatorDataSource
      seed_prices.py       # SEED_PRICES, TICKER_PARAMS, DEFAULT_PARAMS, correlation constants
      stream.py            # create_stream_router() — FastAPI SSE factory
```

Public imports (everything downstream should need):
```python
from app.market import (
    PriceCache,
    PriceUpdate,
    MarketDataSource,
    create_market_data_source,
    create_stream_router,
)
```

---

## Design Decisions

| Decision | Rationale |
|---|---|
| Strategy pattern (ABC) | Swapping simulator ↔ real data requires zero changes to consuming code |
| Cache as single truth | Decouples update frequency (500ms sim vs 15s Massive) from read frequency (500ms SSE) |
| `asyncio.to_thread` for Massive | `RESTClient` is synchronous; blocking the event loop would stall all SSE clients |
| Immediate first poll | Cache has data before the first HTTP client connects; no empty-state edge case |
| `session_open` in cache, not DB | Process-lifetime concept; doesn't need persistence, avoids a DB round-trip on every SSE tick |
| Version counter for SSE | O(1) change detection without price comparisons; SSE loop is allocation-free when no updates |
| Frozen `PriceUpdate` | Prevents accidental mutation by consumers; safe to pass by reference across threads |
