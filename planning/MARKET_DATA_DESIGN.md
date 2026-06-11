# Market Data Backend — Detailed Design

Implementation-ready reference for the FinAlly market data subsystem. All code in
this document reflects the actual implementation in `backend/app/market/`.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [File Structure](#2-file-structure)
3. [Data Model — `models.py`](#3-data-model--modelspy)
4. [Price Cache — `cache.py`](#4-price-cache--cachepy)
5. [Abstract Interface — `interface.py`](#5-abstract-interface--interfacepy)
6. [Seed Prices & Parameters — `seed_prices.py`](#6-seed-prices--parameters--seed_pricespy)
7. [GBM Simulator — `simulator.py`](#7-gbm-simulator--simulatorpy)
8. [Massive API Client — `massive_client.py`](#8-massive-api-client--massive_clientpy)
9. [Factory — `factory.py`](#9-factory--factorypy)
10. [SSE Streaming — `stream.py`](#10-sse-streaming--streampy)
11. [FastAPI Lifecycle Integration](#11-fastapi-lifecycle-integration)
12. [Watchlist Coordination](#12-watchlist-coordination)
13. [Testing Strategy](#13-testing-strategy)
14. [Error Handling & Edge Cases](#14-error-handling--edge-cases)
15. [Configuration Reference](#15-configuration-reference)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  MarketDataSource (ABC)                                  │
│  ├── SimulatorDataSource   ──→  GBMSimulator (500ms)    │
│  └── MassiveDataSource     ──→  Polygon.io REST (15s)   │
│              │                                           │
│              ▼ writes                                    │
│         PriceCache  (thread-safe in-memory)             │
│              │                                           │
│              ├──→ GET /api/stream/prices  (SSE, 500ms)  │
│              ├──→ GET /api/watchlist      (latest price) │
│              ├──→ GET /api/portfolio      (valuation)    │
│              └──→ POST /api/portfolio/trade (execution)  │
└─────────────────────────────────────────────────────────┘
```

**Core design principles:**

- **Strategy pattern**: `SimulatorDataSource` and `MassiveDataSource` implement the same `MarketDataSource` ABC. All downstream code is source-agnostic.
- **Push/pull decoupling**: Data sources push into `PriceCache` on their own schedule. Consumers pull from the cache on theirs. No direct coupling between producers and consumers.
- **Single source of truth**: `PriceCache` is the only place prices live at runtime. Nothing reads from the data source directly.
- **Immediate availability**: Both sources seed the cache before starting their background loop, so SSE and API handlers have data on the very first request.

---

## 2. File Structure

```
backend/
  app/
    market/
      __init__.py          # Re-exports public API
      models.py            # PriceUpdate frozen dataclass
      interface.py         # MarketDataSource ABC
      cache.py             # PriceCache (thread-safe, version counter, session_open)
      seed_prices.py       # SEED_PRICES, TICKER_PARAMS, DEFAULT_PARAMS, correlation constants
      simulator.py         # GBMSimulator + SimulatorDataSource
      massive_client.py    # MassiveDataSource — Polygon.io REST poller
      factory.py           # create_market_data_source() — env-variable dispatch
      stream.py            # create_stream_router() — FastAPI SSE endpoint
```

Public imports — everything downstream needs:

```python
from app.market import (
    PriceUpdate,
    PriceCache,
    MarketDataSource,
    create_market_data_source,
    create_stream_router,
)
```

---

## 3. Data Model — `models.py`

`PriceUpdate` is the **only** type that leaves the market data layer. Every downstream
consumer works exclusively with this type.

```python
# backend/app/market/models.py

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone


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
        """Serialize for JSON / SSE transmission using spec wire field names.

        Wire field names (prev_price, change_pct) match the API spec in PLAN.md §6 and §8.
        session_open comes from PriceCache.get_session_open(), not from this object.
        """
        ts = datetime.fromtimestamp(self.timestamp, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return {
            "ticker": self.ticker,
            "price": self.price,
            "prev_price": self.previous_price,       # wire name: prev_price
            "session_open": session_open if session_open is not None else self.price,
            "change_pct": self.change_percent,        # wire name: change_pct
            "direction": self.direction,
            "timestamp": ts,                          # ISO 8601 string
        }
```

### Wire format example

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

### Design decisions

| Decision | Rationale |
|---|---|
| `frozen=True` | Immutable value object; safe to share across async tasks without copying |
| `slots=True` | Memory optimization — many created per second |
| Computed properties | Derived from `price`/`previous_price`; can never be inconsistent |
| `session_open` is a parameter | It's a process-lifetime concept tracked in `PriceCache`, not in the snapshot itself |
| ISO 8601 timestamp | Spec requires string, not Unix float |

---

## 4. Price Cache — `cache.py`

The price cache is the central data hub. One writer (the active data source); many readers
(SSE, portfolio valuation, trade execution). Must be thread-safe because the Massive client
runs in `asyncio.to_thread()` — a real OS thread — while reads happen on the event loop.

```python
# backend/app/market/cache.py

from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker."""

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
        with self._lock:        # Lock required: version is read from both threads
            return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

### Session open

`session_open` is the price at the **first** observation per ticker per **process lifetime**
(not per calendar day). It resets when the backend restarts. The frontend displays "change
since session start" — this avoids a `price_history` table.

```python
# How session_open is used when building an SSE event:
cache = PriceCache()
cache.update("AAPL", 190.00)   # session_open["AAPL"] = 190.00 (set once)
cache.update("AAPL", 195.50)   # session_open["AAPL"] still 190.00

update = cache.get("AAPL")
session_open = cache.get_session_open("AAPL")
payload = update.to_dict(session_open=session_open)
# → {"ticker": "AAPL", "price": 195.50, "session_open": 190.00, "change_pct": 2.89, ...}
```

### Version counter for SSE change detection

The SSE loop polls the cache every 500ms. The version counter lets it skip serialization
when nothing has changed (e.g., Massive polls every 15s but SSE ticks every 500ms):

```python
last_version = -1
while True:
    current_version = price_cache.version
    if current_version != last_version:
        last_version = current_version
        # Only now do we serialize and send
        for ticker, update in price_cache.get_all().items():
            session_open = price_cache.get_session_open(ticker)
            yield f"data: {json.dumps(update.to_dict(session_open))}\n\n"
    await asyncio.sleep(0.5)
```

### Why `threading.Lock` not `asyncio.Lock`

`asyncio.Lock` only works within a single event loop thread. The Massive client's
`get_snapshot_all()` runs in `asyncio.to_thread()` — a real OS thread — which would
bypass `asyncio.Lock`. `threading.Lock` protects against both OS threads and coroutines.

---

## 5. Abstract Interface — `interface.py`

```python
# backend/app/market/interface.py

from __future__ import annotations

from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    """Contract for market data providers.

    Data sources push price updates into a shared PriceCache on their own
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

### Why push instead of pull

The data source **pushes** into the cache rather than having consumers pull from it.
This decouples update frequency from read frequency:

| Source | Update frequency | SSE read frequency |
|---|---|---|
| Simulator | 500ms | 500ms |
| Massive (free) | 15s | 500ms |
| Massive (paid) | 2–5s | 500ms |

The SSE loop is identical regardless of which source is active.

---

## 6. Seed Prices & Parameters — `seed_prices.py`

Pure constants module — no logic, no imports. Shared by the simulator.

```python
# backend/app/market/seed_prices.py

SEED_PRICES: dict[str, float] = {
    "AAPL":  190.00,
    "GOOGL": 175.00,
    "MSFT":  420.00,
    "AMZN":  185.00,
    "TSLA":  250.00,
    "NVDA":  800.00,
    "META":  500.00,
    "JPM":   195.00,
    "V":     280.00,
    "NFLX":  600.00,
}

# Per-ticker GBM parameters (sigma = annualized volatility, mu = annualized drift)
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT":  {"sigma": 0.20, "mu": 0.05},
    "AMZN":  {"sigma": 0.28, "mu": 0.05},
    "TSLA":  {"sigma": 0.50, "mu": 0.03},   # High volatility, lower drift
    "NVDA":  {"sigma": 0.40, "mu": 0.08},   # High volatility, strong upward drift
    "META":  {"sigma": 0.30, "mu": 0.05},
    "JPM":   {"sigma": 0.18, "mu": 0.04},   # Low volatility (bank)
    "V":     {"sigma": 0.17, "mu": 0.04},   # Low volatility (payments)
    "NFLX":  {"sigma": 0.35, "mu": 0.05},
}

# Applied to any ticker not in the list above (dynamically added tickers)
DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}

# Correlation groups for the Cholesky decomposition
CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech":    {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

INTRA_TECH_CORR    = 0.6   # Tech stocks move together
INTRA_FINANCE_CORR = 0.5   # Finance stocks move together
CROSS_GROUP_CORR   = 0.3   # Between sectors / unknown tickers
TSLA_CORR          = 0.3   # TSLA does its own thing (in tech group but treated as independent)
```

Tickers added dynamically (not in `SEED_PRICES`) start at a random price in `[50, 300]`.

---

## 7. GBM Simulator — `simulator.py`

Two classes in one file:

- **`GBMSimulator`**: Pure math engine — stateful, holds current prices, advances by one tick
- **`SimulatorDataSource`**: Async adapter — wraps `GBMSimulator` in an asyncio loop, writes to `PriceCache`

### 7.1 GBM Math

At each time step a stock price evolves as:

```
S(t+dt) = S(t) * exp((mu - sigma²/2) * dt + sigma * sqrt(dt) * Z)
```

Where:
- `S(t)` — current price
- `mu` — annualized drift (e.g. `0.05` = 5%)
- `sigma` — annualized volatility (e.g. `0.22` = 22%)
- `dt` — time step as fraction of a trading year
- `Z` — standard normal random variable from N(0, 1)

Properties:
- Prices are **always positive** (`exp()` is always > 0)
- Returns are **lognormally distributed** (matches real market data)
- The `(mu - sigma²/2)` term is the Itô correction for continuous-time processes

**Time step calculation:**

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800 seconds

# For 500ms ticks:
dt = 0.5 / TRADING_SECONDS_PER_YEAR  # ≈ 8.48e-8

# With sigma=0.22 (AAPL), per-tick move:
# Expected daily range: sigma * sqrt(1/252) ≈ 1.39%
# Per 500ms tick:       1.39% / (6.5h * 7200 ticks/h) ≈ 0.000030%
# → Sub-cent moves per tick; realistic cumulatively
```

### 7.2 Correlated Moves

Real stocks in the same sector move together. The simulator models this with a Cholesky
decomposition of a correlation matrix.

```
Given correlation matrix C, compute lower triangular L such that C = L @ L.T
To generate n correlated normals from n independent draws:
    Z_correlated = L @ Z_independent
```

Correlation structure:

```python
@staticmethod
def _pairwise_correlation(t1: str, t2: str) -> float:
    tech    = CORRELATION_GROUPS["tech"]
    finance = CORRELATION_GROUPS["finance"]

    if t1 == "TSLA" or t2 == "TSLA":
        return TSLA_CORR          # 0.3 — TSLA does its own thing
    if t1 in tech and t2 in tech:
        return INTRA_TECH_CORR    # 0.6 — tech names move together
    if t1 in finance and t2 in finance:
        return INTRA_FINANCE_CORR # 0.5 — finance names move together
    return CROSS_GROUP_CORR       # 0.3 — cross-sector / unknown
```

### 7.3 Random Events

Every step, each ticker has a 0.1% chance of a sudden shock:

```python
EVENT_PROBABILITY = 0.001  # per tick per ticker

if random.random() < EVENT_PROBABILITY:
    shock_magnitude = random.uniform(0.02, 0.05)   # 2–5% move
    shock_sign = random.choice([-1, 1])
    price *= (1 + shock_magnitude * shock_sign)
```

With 10 tickers at 2 ticks/sec: `10 * 2 * 0.001 = 0.02 events/sec` → one event ~every
50 seconds somewhere on the watchlist. Keeps the UI visually alive.

### 7.4 GBMSimulator Implementation

```python
# backend/app/market/simulator.py

class GBMSimulator:
    """Geometric Brownian Motion simulator with correlated moves."""

    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ~8.48e-8

    def __init__(
        self,
        tickers: list[str],
        dt: float = DEFAULT_DT,
        event_probability: float = 0.001,
    ) -> None:
        self._dt = dt
        self._event_prob = event_probability
        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._cholesky: np.ndarray | None = None

        # Batch initialize: call _add_ticker_internal for each ticker,
        # then build Cholesky once — O(n²) total, not O(n³)
        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def step(self) -> dict[str, float]:
        """Advance all tickers by one dt. Returns {ticker: new_price}.

        Hot path — called every 500ms. O(n) where n = number of tickers.
        """
        n = len(self._tickers)
        if n == 0:
            return {}

        # Generate correlated standard normals
        z_independent = np.random.standard_normal(n)
        z = self._cholesky @ z_independent if self._cholesky is not None else z_independent

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            mu    = self._params[ticker]["mu"]
            sigma = self._params[ticker]["sigma"]

            # GBM: S(t+dt) = S(t) * exp((mu - σ²/2)*dt + σ*sqrt(dt)*Z)
            drift     = (mu - 0.5 * sigma ** 2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            # Random news event
            if random.random() < self._event_prob:
                shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])
                self._prices[ticker] *= (1 + shock)
                logger.debug("Random event on %s: %.1f%%", ticker, shock * 100)

            result[ticker] = round(self._prices[ticker], 2)

        return result

    def add_ticker(self, ticker: str) -> None:
        """Add a ticker. Rebuilds the Cholesky matrix. O(n²), safe for n < 50."""
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker. Rebuilds the Cholesky matrix."""
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    def _add_ticker_internal(self, ticker: str) -> None:
        """Add without rebuilding Cholesky (used during batch initialization)."""
        if ticker in self._prices:
            return
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        """Rebuild the Cholesky factor of the correlation matrix."""
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return
        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = rho
                corr[j, i] = rho
        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        tech    = CORRELATION_GROUPS["tech"]
        finance = CORRELATION_GROUPS["finance"]
        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR
        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR
```

### 7.5 SimulatorDataSource — Async Wrapper

```python
class SimulatorDataSource(MarketDataSource):
    """Wraps GBMSimulator in an asyncio background task."""

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
        # dt is derived from the actual update_interval, keeping GBM math consistent
        dt = self._interval / GBMSimulator.TRADING_SECONDS_PER_YEAR
        self._sim = GBMSimulator(tickers=tickers, dt=dt, event_probability=self._event_prob)

        # Seed the cache immediately — SSE has data before the loop's first tick
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)

        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")
        logger.info("Simulator started with %d tickers", len(tickers))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Simulator stopped")

    async def add_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.add_ticker(ticker)
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)  # Seed immediately
            logger.info("Simulator: added ticker %s", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._cache.remove(ticker)
        logger.info("Simulator: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        while True:
            try:
                if self._sim:
                    prices = self._sim.step()
                    for ticker, price in prices.items():
                        self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

Key behaviors:

| Behavior | Detail |
|---|---|
| Immediate seeding | Cache populated before loop starts — no blank-screen on first connect |
| `dt` derived from interval | GBM math matches simulated clock rate; changing interval doesn't distort moves |
| Graceful stop | `cancel()` + `await` + catch `CancelledError`; clean shutdown during FastAPI lifespan |
| Exception resilience | Loop catches per-step exceptions; one bad tick doesn't kill the feed |
| `asyncio.sleep` after step | First update happens without delay |

---

## 8. Massive API Client — `massive_client.py`

Polls the Massive (formerly Polygon.io) REST snapshot endpoint. The synchronous Massive
client runs in `asyncio.to_thread()` to avoid blocking the event loop.

```python
# backend/app/market/massive_client.py

from massive import RESTClient
from massive.rest.models import SnapshotMarketType


class MassiveDataSource(MarketDataSource):
    """MarketDataSource backed by the Massive (Polygon.io) REST API.

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
        # Idempotency guard: prevents double-initialization if called twice
        if self._task and not self._task.done():
            logger.warning("Massive poller already running; ignoring start()")
            return

        self._client = RESTClient(api_key=self._api_key)
        self._tickers = [t.upper().strip() for t in tickers]

        # Immediate first poll: cache has data before the first SSE client connects
        await self._poll_once()

        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info("Massive poller started: %d tickers, %.1fs interval",
                    len(tickers), self._interval)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None
        logger.info("Massive poller stopped")

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)
            logger.info("Massive: added ticker %s (will appear on next poll)", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)
        logger.info("Massive: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    async def _poll_loop(self) -> None:
        """First poll already happened in start(). Loop starts from sleep."""
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        """Fetch snapshots for all tickers and update the cache."""
        if not self._tickers or not self._client:
            return

        try:
            # RESTClient is synchronous — run in a thread to avoid blocking the event loop
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            processed = 0
            for snap in snapshots:
                try:
                    price = snap.last_trade.price
                    # Massive v2 timestamps are Unix milliseconds → convert to seconds
                    timestamp = snap.last_trade.timestamp / 1000.0
                    self._cache.update(ticker=snap.ticker, price=price, timestamp=timestamp)
                    processed += 1
                except (AttributeError, TypeError) as e:
                    logger.warning("Skipping snapshot for %s: %s",
                                   getattr(snap, "ticker", "???"), e)
            logger.debug("Massive poll: updated %d/%d tickers", processed, len(self._tickers))

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

### Snapshot response fields

The v2 snapshot endpoint (`GET /v2/snapshot/locale/us/markets/stocks/tickers`) returns:

| Field | Type | Description |
|---|---|---|
| `snap.ticker` | str | Ticker symbol |
| `snap.last_trade.price` | float | Most recent trade price ← **used** |
| `snap.last_trade.timestamp` | int | Unix **milliseconds** ← **used** (÷1000 for seconds) |
| `snap.last_trade.size` | int | Trade size (shares) |
| `snap.day.open` | float | Day open |
| `snap.day.change_percent` | float | Day % change |

FinAlly extracts only `last_trade.price` and `last_trade.timestamp`.

### Error handling

| Error | Behavior |
|---|---|
| 401 Unauthorized (bad key) | Logged as error; poller keeps running |
| 429 Rate Limited | Logged as error; retries after `poll_interval` |
| Network timeout | Logged as error; retries automatically |
| Malformed snapshot | Individual ticker skipped with warning; others proceed |
| All tickers fail | Cache retains last-known prices; SSE keeps streaming stale data |

### Why `asyncio.to_thread()`

```python
# RESTClient is synchronous. Calling it directly would block the event loop:
#   snapshots = client.get_snapshot_all(...)  # BAD: blocks all coroutines

# asyncio.to_thread runs it in a thread pool executor:
snapshots = await asyncio.to_thread(self._fetch_snapshots)  # GOOD: event loop stays alive
```

### Why v2 over v3

FinAlly uses `get_snapshot_all()` (v2) because it returns all requested tickers in a
single non-paginated response. v3's `list_universal_snapshots()` auto-paginates (250
tickers per page) — unnecessary complexity for a small watchlist.

---

## 9. Factory — `factory.py`

```python
# backend/app/market/factory.py

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Select the appropriate market data source based on environment.

    - MASSIVE_API_KEY set and non-empty  →  MassiveDataSource (real data, 15s poll)
    - Otherwise                          →  SimulatorDataSource (GBM, 500ms tick)

    Returns an unstarted source; caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(price_cache=price_cache)
```

Usage:

```python
cache = PriceCache()
source = create_market_data_source(cache)
await source.start(["AAPL", "GOOGL", "MSFT", ...])
# source is now running; cache receives price updates
```

---

## 10. SSE Streaming — `stream.py`

The SSE endpoint holds open a long-lived HTTP connection and pushes one event per ticker
per 500ms cadence.

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
    """Factory: returns an APIRouter with the SSE endpoint wired to this cache.

    A fresh router is created each call to avoid double-registration.
    """
    router = APIRouter(prefix="/api/stream", tags=["streaming"])

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(
    price_cache: PriceCache,
    request: Request,
    interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    """Yields SSE events: one JSON object per ticker per interval.

    Uses the cache version counter to detect updates without comparing prices.
    Stops cleanly when the client disconnects.
    """
    yield "retry: 1000\n\n"   # Tell the browser to reconnect after 1s if dropped

    last_version = -1
    client_ip = request.client.host if request.client else "unknown"
    logger.info("SSE client connected: %s", client_ip)

    try:
        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected: %s", client_ip)
                break

            try:
                current_version = price_cache.version
                if current_version != last_version:
                    last_version = current_version
                    prices = price_cache.get_all()
                    for ticker, update in prices.items():
                        session_open = price_cache.get_session_open(ticker)
                        payload = json.dumps(update.to_dict(session_open=session_open))
                        yield f"data: {payload}\n\n"
            except Exception:
                logger.exception("SSE stream error for %s", client_ip)

            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for: %s", client_ip)
```

### SSE wire format

Each event is a single `data:` line with one ticker's JSON:

```
retry: 1000

data: {"ticker": "AAPL", "price": 195.50, "prev_price": 194.20, "session_open": 190.00, "change_pct": 2.89, "direction": "up", "timestamp": "2026-01-01T10:00:00Z"}

data: {"ticker": "GOOGL", "price": 175.12, "prev_price": 175.00, "session_open": 174.50, "change_pct": 0.07, "direction": "up", "timestamp": "2026-01-01T10:00:00Z"}

```

Events are emitted **per ticker** (not batched). The frontend processes them one at a time:

```javascript
const eventSource = new EventSource('/api/stream/prices');
eventSource.onmessage = (event) => {
    const update = JSON.parse(event.data);
    // update = { ticker: "AAPL", price: 195.50, prev_price: 194.20, ... }
    store.updatePrice(update.ticker, update);
};
```

### SSE connection status

The frontend displays a colored dot using EventSource lifecycle events:

```javascript
eventSource.onopen  = () => setStatus("connected");     // green
eventSource.onerror = () => setStatus("reconnecting");  // yellow
// After retry: 1000, browser auto-reconnects → onopen fires again
```

---

## 11. FastAPI Lifecycle Integration

The market data system starts and stops with the FastAPI application:

```python
# backend/app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.market import PriceCache, create_market_data_source, create_stream_router

DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    price_cache = PriceCache()
    source = create_market_data_source(price_cache)

    # Load initial tickers from DB watchlist (or use defaults if DB empty)
    initial_tickers = await load_watchlist_from_db() or DEFAULT_TICKERS
    await source.start(initial_tickers)

    app.state.price_cache = price_cache
    app.state.market_source = source

    # Register SSE router after source starts (cache already has seed data)
    stream_router = create_stream_router(price_cache)
    app.include_router(stream_router)

    yield  # App runs here

    # SHUTDOWN
    await source.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)


# FastAPI dependency helpers for route handlers
def get_price_cache(request: Request) -> PriceCache:
    return request.app.state.price_cache

def get_market_source(request: Request) -> MarketDataSource:
    return request.app.state.market_source
```

### Accessing market data from route handlers

```python
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api")


@router.post("/portfolio/trade")
async def execute_trade(
    trade: TradeRequest,
    price_cache: PriceCache = Depends(get_price_cache),
):
    current_price = price_cache.get_price(trade.ticker)
    if current_price is None:
        raise HTTPException(400, f"No price available for {trade.ticker}. Try again shortly.")
    # ... execute at current_price ...


@router.get("/watchlist")
async def get_watchlist(
    price_cache: PriceCache = Depends(get_price_cache),
):
    # Enrich watchlist rows with live prices from cache
    tickers = await db.get_watchlist()
    result = []
    for ticker in tickers:
        update = price_cache.get(ticker)
        session_open = price_cache.get_session_open(ticker)
        result.append({
            "ticker": ticker,
            "price": update.price if update else None,
            "prev_price": update.previous_price if update else None,
            "session_open": session_open,
            "change_pct": update.change_percent if update else 0.0,
        })
    return result
```

---

## 12. Watchlist Coordination

When the watchlist changes (via REST API or LLM chat), the market data source must be
notified to track the right set of tickers.

### Adding a ticker

```
POST /api/watchlist {"ticker": "PYPL"}
  → Validate ticker format (1–10 uppercase alphanumeric)
  → INSERT into watchlist table (SQLite)
  → await source.add_ticker("PYPL")
      Simulator: adds to GBMSimulator, rebuilds Cholesky, seeds cache immediately
      Massive:   appends to ticker list; appears in cache on next poll (≤15s)
  → Return {ticker, price} (price may be None briefly for Massive)
```

### Removing a ticker

```
DELETE /api/watchlist/PYPL
  → DELETE from watchlist table (SQLite)
  → Check: does user hold shares of PYPL?
      If yes: keep tracking (portfolio valuation needs the price)
      If no:  await source.remove_ticker("PYPL") → removes from cache too
  → Return {"ok": true}
```

### Edge case: open position in removed ticker

```python
@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    source: MarketDataSource = Depends(get_market_source),
):
    await db.delete_watchlist_entry(ticker)

    # Only stop tracking if no open position
    position = await db.get_position(ticker)
    if position is None or position.quantity == 0:
        await source.remove_ticker(ticker)

    return {"ok": True}
```

---

## 13. Testing Strategy

The market data layer has 79 passing tests. Key test patterns:

### 13.1 GBMSimulator unit tests

```python
# backend/tests/market/test_simulator.py
import pytest
from app.market.simulator import GBMSimulator
from app.market.seed_prices import SEED_PRICES


class TestGBMSimulator:

    def test_step_returns_all_tickers(self):
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        result = sim.step()
        assert set(result.keys()) == {"AAPL", "GOOGL"}

    def test_prices_always_positive(self):
        """GBM exp() is always positive; prices can never go to zero."""
        sim = GBMSimulator(tickers=["AAPL"])
        for _ in range(10_000):
            prices = sim.step()
            assert prices["AAPL"] > 0

    def test_initial_prices_match_seeds(self):
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim.get_price("AAPL") == SEED_PRICES["AAPL"]

    def test_add_ticker_appears_in_next_step(self):
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("TSLA")
        result = sim.step()
        assert "TSLA" in result

    def test_remove_ticker_absent_from_next_step(self):
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        sim.remove_ticker("GOOGL")
        result = sim.step()
        assert "GOOGL" not in result

    def test_add_duplicate_is_noop(self):
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("AAPL")
        assert len(sim._tickers) == 1

    def test_unknown_ticker_random_seed_price(self):
        sim = GBMSimulator(tickers=["ZZZZ"])
        price = sim.get_price("ZZZZ")
        assert 50.0 <= price <= 300.0

    def test_empty_step(self):
        sim = GBMSimulator(tickers=[])
        assert sim.step() == {}

    def test_cholesky_none_for_single_ticker(self):
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim._cholesky is None  # No correlation matrix for 1 ticker

    def test_cholesky_built_for_two_tickers(self):
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        assert sim._cholesky is not None
```

### 13.2 PriceCache unit tests

```python
# backend/tests/market/test_cache.py
from app.market.cache import PriceCache


class TestPriceCache:

    def test_first_update_is_flat(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.00)
        assert update.direction == "flat"
        assert update.previous_price == 190.00

    def test_direction_up(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        update = cache.update("AAPL", 191.00)
        assert update.direction == "up"
        assert update.change == 1.00

    def test_session_open_set_once(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("AAPL", 195.00)
        assert cache.get_session_open("AAPL") == 190.00  # Never overwritten

    def test_remove_clears_session_open(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.remove("AAPL")
        assert cache.get("AAPL") is None
        assert cache.get_session_open("AAPL") is None

    def test_version_increments_per_update(self):
        cache = PriceCache()
        v0 = cache.version
        cache.update("AAPL", 190.00)
        assert cache.version == v0 + 1
        cache.update("AAPL", 191.00)
        assert cache.version == v0 + 2

    def test_get_all_returns_copy(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        all_prices = cache.get_all()
        all_prices.pop("AAPL")  # Mutate the copy
        assert cache.get("AAPL") is not None  # Original unaffected
```

### 13.3 SimulatorDataSource integration tests

```python
# backend/tests/market/test_simulator_source.py
import asyncio
import pytest
from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource


@pytest.mark.asyncio
class TestSimulatorDataSource:

    async def test_start_seeds_cache_immediately(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "GOOGL"])

        # Seed prices are in cache before any loop tick
        assert cache.get("AAPL") is not None
        assert cache.get("GOOGL") is not None
        await source.stop()

    async def test_stop_is_idempotent(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])
        await source.stop()
        await source.stop()  # Second stop should not raise

    async def test_add_ticker_seeds_cache(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.5)
        await source.start(["AAPL"])

        await source.add_ticker("TSLA")
        assert cache.get("TSLA") is not None  # Seeded immediately
        assert "TSLA" in source.get_tickers()
        await source.stop()

    async def test_remove_ticker_clears_cache(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.5)
        await source.start(["AAPL", "TSLA"])

        await source.remove_ticker("TSLA")
        assert cache.get("TSLA") is None
        assert "TSLA" not in source.get_tickers()
        await source.stop()
```

### 13.4 MassiveDataSource tests (mocked)

```python
# backend/tests/market/test_massive.py
from unittest.mock import MagicMock, patch
import pytest
from app.market.cache import PriceCache
from app.market.massive_client import MassiveDataSource


def _make_snapshot(ticker: str, price: float, timestamp_ms: int) -> MagicMock:
    snap = MagicMock()
    snap.ticker = ticker
    snap.last_trade.price = price
    snap.last_trade.timestamp = timestamp_ms
    return snap


@pytest.mark.asyncio
class TestMassiveDataSource:

    async def test_poll_updates_cache(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=999)
        source._tickers = ["AAPL", "GOOGL"]
        source._client = MagicMock()

        snapshots = [
            _make_snapshot("AAPL", 190.50, 1_707_580_800_000),
            _make_snapshot("GOOGL", 175.25, 1_707_580_800_000),
        ]

        with patch.object(source, "_fetch_snapshots", return_value=snapshots):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("GOOGL") == 175.25

    async def test_timestamp_converted_from_ms_to_seconds(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=999)
        source._tickers = ["AAPL"]
        source._client = MagicMock()

        ts_ms = 1_707_580_800_000  # Unix ms
        snapshots = [_make_snapshot("AAPL", 190.50, ts_ms)]

        with patch.object(source, "_fetch_snapshots", return_value=snapshots):
            await source._poll_once()

        update = cache.get("AAPL")
        assert update.timestamp == pytest.approx(ts_ms / 1000.0)

    async def test_malformed_snapshot_skipped(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=999)
        source._tickers = ["AAPL", "BAD"]
        source._client = MagicMock()

        good_snap = _make_snapshot("AAPL", 190.50, 1_707_580_800_000)
        bad_snap = MagicMock()
        bad_snap.ticker = "BAD"
        bad_snap.last_trade = None  # AttributeError on .price

        with patch.object(source, "_fetch_snapshots", return_value=[good_snap, bad_snap]):
            await source._poll_once()  # Should not raise

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("BAD") is None

    async def test_api_error_does_not_crash_loop(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=999)
        source._tickers = ["AAPL"]
        source._client = MagicMock()

        with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
            await source._poll_once()  # Should not raise

    async def test_start_idempotent(self):
        """Second call to start() while already running is a no-op."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=999)

        with patch.object(source, "_poll_once"):
            with patch("massive.RESTClient"):
                await source.start(["AAPL"])
                task_id = id(source._task)
                await source.start(["AAPL"])  # Second call
                assert id(source._task) == task_id  # Same task, not replaced

        await source.stop()
```

---

## 14. Error Handling & Edge Cases

### Empty watchlist on startup

Both sources handle `start([])` gracefully — the simulator produces no prices, Massive
skips its API call. SSE sends no data events. When the user adds the first ticker, the
source starts tracking it immediately.

### Price cache miss during trade execution

```python
current_price = price_cache.get_price(ticker)
if current_price is None:
    raise HTTPException(
        status_code=400,
        detail=f"Price not yet available for {ticker}. Please wait a moment and try again.",
    )
```

The simulator never has this problem (seeds cache in `add_ticker()`). The Massive client
may have a brief gap — up to 15s on the free tier.

### Invalid Massive API key

First poll fails with HTTP 401. The poller logs the error and keeps retrying every 15s.
SSE streams empty data. The fix is to correct `MASSIVE_API_KEY` in `.env` and restart.

### Simulator floating-point precision

GBM with tiny `dt` produces very small per-tick moves. No precision issues because:
- Prices are `round()`ed to 2 decimal places in `GBMSimulator.step()`
- The `exp()` formulation is numerically stable
- Prices are always positive (exponential function)

### Thread safety under load

`threading.Lock` is a mutex — one thread at a time. The critical section is tiny (dict
lookup + assignment). At 10 tickers × 2 updates/sec, lock contention is negligible.

---

## 15. Configuration Reference

All tunable parameters and their defaults:

| Parameter | Location | Default | Description |
|---|---|---|---|
| `MASSIVE_API_KEY` | `.env` | `""` (empty) | If set, use Massive API; otherwise simulator |
| `update_interval` | `SimulatorDataSource.__init__` | `0.5` s | Time between simulator ticks |
| `poll_interval` | `MassiveDataSource.__init__` | `15.0` s | Time between Massive API polls |
| `event_probability` | `GBMSimulator.__init__` | `0.001` | Chance of random shock per ticker per tick |
| `dt` | `GBMSimulator.__init__` | `~8.48e-8` | GBM time step (fraction of a trading year) |
| SSE push interval | `_generate_events()` | `0.5` s | Time between SSE pushes per client |
| SSE retry directive | `_generate_events()` | `1000` ms | Browser EventSource reconnection delay |

### Behavior comparison

| Property | Simulator | Massive (free) | Massive (paid) |
|---|---|---|---|
| Update frequency | 500ms | 15s | 2–5s |
| External dependency | numpy only | `massive` package + API key | same |
| Price accuracy | Synthetic GBM | Real last-trade price | Real last-trade price |
| Random events | Yes (0.1%/tick) | No | No |
| Cold-start data | Immediate (seed prices) | After first poll (~15s) | After first poll (~2–5s) |
| `session_open` | Set on first `update()` | Set on first poll | Set on first poll |
