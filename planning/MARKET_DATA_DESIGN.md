# Market Data Backend — Design & Implementation Guide

Complete reference for the `backend/app/market/` subsystem. Covers the unified interface, price cache, GBM simulator, Massive API client, SSE streaming, and FastAPI lifecycle integration. This component is **fully implemented and tested** — use this document as a reference when integrating from other parts of the backend.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [File Structure](#2-file-structure)
3. [Data Model — `models.py`](#3-data-model)
4. [Price Cache — `cache.py`](#4-price-cache)
5. [Abstract Interface — `interface.py`](#5-abstract-interface)
6. [Seed Prices & Parameters — `seed_prices.py`](#6-seed-prices--parameters)
7. [GBM Simulator — `simulator.py`](#7-gbm-simulator)
8. [Massive API Client — `massive_client.py`](#8-massive-api-client)
9. [Factory — `factory.py`](#9-factory)
10. [SSE Streaming — `stream.py`](#10-sse-streaming)
11. [FastAPI Lifecycle Integration](#11-fastapi-lifecycle-integration)
12. [Watchlist Coordination](#12-watchlist-coordination)
13. [Error Handling](#13-error-handling)
14. [Configuration Reference](#14-configuration-reference)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ MarketDataSource (ABC)                                          │
│   ├── SimulatorDataSource  — GBM simulation (default)          │
│   └── MassiveDataSource    — Polygon.io REST poller            │
│                │                                               │
│                ▼ writes to                                      │
│          PriceCache (thread-safe, in-memory)                   │
│                │                                               │
│     ┌──────────┼───────────────┐                               │
│     ▼          ▼               ▼                               │
│ SSE stream  Portfolio       Trade execution                    │
│ /api/stream/prices  valuation  /api/portfolio/trade            │
└─────────────────────────────────────────────────────────────────┘
```

**Key design principles:**

- **Strategy pattern**: both data sources implement the same ABC; all downstream code is source-agnostic
- **Push model**: sources write to `PriceCache` on their own schedule; consumers read at theirs
- **Single version counter**: SSE detects changes cheaply without serializing all prices every tick
- **Thread-safe cache**: uses `threading.Lock` (not `asyncio.Lock`) because the Massive client's synchronous REST call runs in `asyncio.to_thread()`

---

## 2. File Structure

```
backend/app/market/
  __init__.py          # Public API re-exports
  models.py            # PriceUpdate — immutable frozen dataclass
  cache.py             # PriceCache — thread-safe in-memory store
  interface.py         # MarketDataSource — abstract base class
  seed_prices.py       # Seed prices, GBM params, correlation groups
  simulator.py         # GBMSimulator + SimulatorDataSource
  massive_client.py    # MassiveDataSource — REST polling client
  factory.py           # create_market_data_source() — env-based factory
  stream.py            # create_stream_router() — FastAPI SSE endpoint
```

Import from the package, not submodules:

```python
from app.market import PriceCache, create_market_data_source, create_stream_router
```

---

## 3. Data Model

**`backend/app/market/models.py`**

`PriceUpdate` is the only data type that leaves the market data layer. Every downstream consumer works exclusively with this type.

```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: float  # Unix seconds (default: time.time())

    @property
    def change(self) -> float: ...          # price - previous_price, rounded to 2dp
    @property
    def change_percent(self) -> float: ...  # percent change, rounded to 2dp
    @property
    def direction(self) -> str: ...         # "up", "down", or "flat"

    def to_dict(self, session_open: float | None = None) -> dict:
        """Serialize to SSE/JSON wire format. Uses spec field names."""
```

The `to_dict()` output matches the exact wire contract in PLAN.md §6:

```json
{
  "ticker": "AAPL",
  "price": 195.50,
  "prev_price": 194.20,
  "session_open": 190.00,
  "change_pct": 0.68,
  "direction": "up",
  "timestamp": "2026-01-01T10:00:00Z"
}
```

Note: `timestamp` is an ISO 8601 string (`"2026-01-01T10:00:00Z"`), not a Unix float. The `session_open` parameter is passed in by the SSE emitter from `PriceCache.get_session_open()`.

---

## 4. Price Cache

**`backend/app/market/cache.py`**

The single shared data hub. Sources write; consumers read.

```python
class PriceCache:
    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price. On first update for a ticker: previous_price == price, direction == "flat".
        Sets session_open the first time a ticker is seen — never overwritten.
        """

    def get(self, ticker: str) -> PriceUpdate | None: ...
    def get_price(self, ticker: str) -> float | None: ...       # Convenience
    def get_all(self) -> dict[str, PriceUpdate]: ...            # Shallow copy snapshot
    def get_session_open(self, ticker: str) -> float | None: ...# First price this process lifetime
    def remove(self, ticker: str) -> None: ...                  # Also removes from session_open

    @property
    def version(self) -> int: ...  # Monotonically increasing; bumped on every update
```

### Session open tracking

`session_open` is the price at first observation in the current process lifetime — it resets on backend restart, not at midnight. It enables the frontend to show "change since session start."

```python
# session_open is set once and never overwritten:
if ticker not in self._session_open:
    self._session_open[ticker] = round(price, 2)
```

### Version counter for SSE efficiency

The SSE loop uses the version counter to skip sends when nothing changed (important when using the Massive API which only updates every 15 seconds):

```python
last_version = -1
while True:
    current_version = price_cache.version
    if current_version != last_version:
        last_version = current_version
        # emit events
    await asyncio.sleep(0.5)
```

### Thread safety

Uses `threading.Lock` (not `asyncio.Lock`) because `MassiveDataSource._fetch_snapshots()` runs in a real OS thread via `asyncio.to_thread()`. `asyncio.Lock` does not protect against that.

---

## 5. Abstract Interface

**`backend/app/market/interface.py`**

```python
class MarketDataSource(ABC):
    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates. Call exactly once."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop background task. Safe to call multiple times."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker. Also removes from PriceCache."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Current list of actively tracked tickers."""
```

Downstream code (watchlist routes, portfolio valuation) always types against `MarketDataSource`, never against the concrete implementations.

---

## 6. Seed Prices & Parameters

**`backend/app/market/seed_prices.py`**

Constants only — no logic. Shared by both the simulator and the Massive client (as fallback seeds).

```python
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00, "GOOGL": 175.00, "MSFT": 420.00, "AMZN": 185.00,
    "TSLA": 250.00, "NVDA": 800.00,  "META": 500.00, "JPM":  195.00,
    "V":    280.00, "NFLX": 600.00,
}

# Per-ticker annualized GBM parameters
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"sigma": 0.22, "mu": 0.05},  # sigma = volatility, mu = drift
    "TSLA":  {"sigma": 0.50, "mu": 0.03},  # High volatility
    "NVDA":  {"sigma": 0.40, "mu": 0.08},  # High volatility, strong drift
    "JPM":   {"sigma": 0.18, "mu": 0.04},  # Low volatility (bank)
    # ... etc
}

DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}  # Unknown tickers

CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech":    {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

INTRA_TECH_CORR    = 0.6   # Tech stocks move together
INTRA_FINANCE_CORR = 0.5   # Finance stocks move together
CROSS_GROUP_CORR   = 0.3   # Between sectors / TSLA / unknown
TSLA_CORR          = 0.3   # TSLA does its own thing
```

---

## 7. GBM Simulator

**`backend/app/market/simulator.py`**

Two classes: `GBMSimulator` (pure math engine) and `SimulatorDataSource` (async wrapper).

### 7.1 GBMSimulator — Math Engine

Models stock price evolution using Geometric Brownian Motion with Cholesky-correlated moves across tickers:

```
S(t+dt) = S(t) * exp((mu - σ²/2) * dt + σ * √dt * Z)
```

where `Z` is a correlated standard normal drawn via Cholesky decomposition of the inter-ticker correlation matrix.

```python
class GBMSimulator:
    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ~8.48e-8 (one 500ms tick)

    def step(self) -> dict[str, float]:
        """Advance all tickers one tick. Returns {ticker: new_price}. Hot path."""
        n = len(self._tickers)
        z_independent = np.random.standard_normal(n)
        z_correlated = self._cholesky @ z_independent  # Apply correlation

        for i, ticker in enumerate(self._tickers):
            mu, sigma = params["mu"], params["sigma"]
            drift     = (mu - 0.5 * sigma**2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z_correlated[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            # Random shock: ~0.1% chance per tick per ticker → ~1 event per 50s
            if random.random() < self._event_prob:
                shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])
                self._prices[ticker] *= (1 + shock)

        return {ticker: round(price, 2) for ticker, price in self._prices.items()}

    def add_ticker(self, ticker: str) -> None:
        """Adds ticker, rebuilds Cholesky. O(n²) but n < 50."""

    def remove_ticker(self, ticker: str) -> None:
        """Removes ticker, rebuilds Cholesky."""

    def get_price(self, ticker: str) -> float | None: ...
    def get_tickers(self) -> list[str]: ...
```

**Key behaviors:**
- Prices are always positive (exponential function)
- `dt` is tiny (~8.5e-8) so per-tick moves are sub-cent and accumulate naturally
- Random events fire with ~0.1% chance per ticker per tick — with 10 tickers at 2 ticks/s, expect roughly one event every 50 seconds
- Cholesky is rebuilt O(n²) on add/remove; negligible for n < 50

### 7.2 SimulatorDataSource — Async Wrapper

```python
class SimulatorDataSource(MarketDataSource):
    def __init__(self, price_cache: PriceCache, update_interval: float = 0.5,
                 event_probability: float = 0.001): ...

    async def start(self, tickers: list[str]) -> None:
        # 1. Create GBMSimulator
        # 2. Seed cache with initial prices IMMEDIATELY (no blank-screen delay)
        # 3. Launch asyncio background task
        self._sim = GBMSimulator(tickers=tickers)
        for ticker in tickers:
            self._cache.update(ticker=ticker, price=self._sim.get_price(ticker))
        self._task = asyncio.create_task(self._run_loop())

    async def _run_loop(self) -> None:
        while True:
            try:
                prices = self._sim.step()
                for ticker, price in prices.items():
                    self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")  # Never crash the loop
            await asyncio.sleep(self._interval)
```

`stop()` cancels the task and awaits `CancelledError` for clean shutdown.

---

## 8. Massive API Client

**`backend/app/market/massive_client.py`**

Polls the Polygon.io REST snapshot endpoint via the `massive` Python package.

```python
class MassiveDataSource(MarketDataSource):
    def __init__(self, api_key: str, price_cache: PriceCache, poll_interval: float = 15.0): ...
        # Free tier: 5 req/min → 15s interval
        # Paid tiers: can reduce to 2–5s

    async def start(self, tickers: list[str]) -> None:
        from massive import RESTClient                 # Lazy import — only when API key set
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = list(tickers)
        await self._poll_once()                        # Seed cache immediately
        self._task = asyncio.create_task(self._poll_loop())

    async def _poll_once(self) -> None:
        # Run synchronous Massive client in a thread (non-blocking)
        snapshots = await asyncio.to_thread(self._fetch_snapshots)
        for snap in snapshots:
            self._cache.update(
                ticker=snap.ticker,
                price=snap.last_trade.price,
                timestamp=snap.last_trade.timestamp / 1000.0,  # ms → seconds
            )

    def _fetch_snapshots(self) -> list:
        """Synchronous. Runs in asyncio.to_thread()."""
        from massive.rest.models import SnapshotMarketType
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

**Error handling philosophy** — the poller never crashes on API errors:

| Error | Behavior |
|-------|----------|
| 401 Unauthorized | Logged as error; loop continues (fix key and restart) |
| 429 Rate Limited | Logged as error; retries on next interval |
| Network timeout | Logged as error; retries on next interval |
| Malformed snapshot | Individual ticker skipped with warning; others still processed |
| All tickers fail | Cache retains last-known prices; SSE keeps streaming stale data |

**Lazy import:** `from massive import RESTClient` only happens inside `start()`. Students without a Massive API key never need the package installed. The simulator path has zero external dependencies beyond `numpy`.

---

## 9. Factory

**`backend/app/market/factory.py`**

```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Select simulator or Massive based on MASSIVE_API_KEY env var."""
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        from .massive_client import MassiveDataSource
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        from .simulator import SimulatorDataSource
        return SimulatorDataSource(price_cache=price_cache)
```

Returns an **unstarted** source. The caller must `await source.start(tickers)`.

---

## 10. SSE Streaming

**`backend/app/market/stream.py`**

```python
def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Factory: returns a FastAPI router with GET /api/stream/prices registered."""
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
```

```python
async def _generate_events(
    price_cache: PriceCache, request: Request, interval: float = 0.5
) -> AsyncGenerator[str, None]:
    yield "retry: 1000\n\n"           # Tell browser to reconnect after 1s if dropped

    last_version = -1
    while True:
        if await request.is_disconnected():
            break

        current_version = price_cache.version
        if current_version != last_version:
            last_version = current_version
            prices = price_cache.get_all()
            for ticker, update in prices.items():
                session_open = price_cache.get_session_open(ticker)
                payload = json.dumps(update.to_dict(session_open=session_open))
                yield f"data: {payload}\n\n"  # One event per ticker per cadence

        await asyncio.sleep(interval)
```

### Wire format

One SSE event per ticker per 500ms cadence:

```
data: {"ticker":"AAPL","price":195.50,"prev_price":194.20,"session_open":190.00,"change_pct":0.68,"direction":"up","timestamp":"2026-01-01T10:00:00Z"}

data: {"ticker":"GOOGL","price":175.12,...}

```

### Frontend consumption

```javascript
const eventSource = new EventSource('/api/stream/prices');
eventSource.onmessage = (event) => {
    const update = JSON.parse(event.data);  // One ticker object per event
    // update.ticker, update.price, update.prev_price, update.session_open,
    // update.change_pct, update.direction, update.timestamp
};
```

EventSource handles reconnection automatically. The `retry: 1000` directive configures the reconnection delay.

---

## 11. FastAPI Lifecycle Integration

**`backend/app/main.py`** (pattern to implement):

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.market import PriceCache, create_market_data_source, create_stream_router

price_cache: PriceCache
market_source: MarketDataSource

@asynccontextmanager
async def lifespan(app: FastAPI):
    global price_cache, market_source

    # 1. Create cache
    price_cache = PriceCache()

    # 2. Load initial tickers from DB
    initial_tickers = await db.get_watchlist_tickers()

    # 3. Create and start source (reads MASSIVE_API_KEY from env)
    market_source = create_market_data_source(price_cache)
    await market_source.start(initial_tickers)

    # 4. Register SSE router
    app.include_router(create_stream_router(price_cache))

    yield  # App is running

    # 5. Clean shutdown
    await market_source.stop()

app = FastAPI(title="FinAlly", lifespan=lifespan)
```

### Dependency injection pattern

Expose cache and source via FastAPI dependencies so route handlers can access them:

```python
def get_price_cache() -> PriceCache:
    return price_cache

def get_market_source() -> MarketDataSource:
    return market_source

# In a route:
@router.post("/portfolio/trade")
async def execute_trade(
    trade: TradeRequest,
    cache: PriceCache = Depends(get_price_cache),
):
    current_price = cache.get_price(trade.ticker)
    if current_price is None:
        raise HTTPException(400, f"Price not yet available for {trade.ticker}")
    # ... execute at current_price ...
```

---

## 12. Watchlist Coordination

When the watchlist changes, the market source must be notified to track the right tickers.

### Adding a ticker

```python
@router.post("/api/watchlist")
async def add_ticker(
    payload: WatchlistAdd,
    source: MarketDataSource = Depends(get_market_source),
):
    # 1. Validate and insert into DB
    await db.insert_watchlist_entry(payload.ticker)

    # 2. Tell source to start tracking (simulator seeds cache immediately;
    #    Massive will include on next poll)
    await source.add_ticker(payload.ticker)

    return {"ok": True}
```

### Removing a ticker

```python
@router.delete("/api/watchlist/{ticker}")
async def remove_ticker(
    ticker: str,
    source: MarketDataSource = Depends(get_market_source),
):
    await db.delete_watchlist_entry(ticker)

    # Only stop tracking if no open position (price still needed for portfolio valuation)
    position = await db.get_position(ticker)
    if position is None or position.quantity == 0:
        await source.remove_ticker(ticker)  # Also removes from PriceCache

    return {"ok": True}
```

---

## 13. Error Handling

### Startup: empty watchlist

If the user has deleted all tickers, `start([])` is safe — both sources handle empty lists gracefully. SSE sends no events. When the user adds a ticker, `add_ticker()` starts tracking it immediately.

### Price cache miss during trade

The simulator seeds the cache in `start()` and `add_ticker()`, so misses are rare but possible when using the Massive client (15s poll interval):

```python
price = cache.get_price(ticker)
if price is None:
    raise HTTPException(400, {"ok": False, "error": f"Price not yet available for {ticker}. Try again shortly."})
```

### Simulator precision

GBM with tiny `dt` (~8.5e-8) produces sub-cent moves per tick. Prices are `round()`-ed to 2dp after each step. The exponential formulation is always positive and numerically stable.

---

## 14. Configuration Reference

| Parameter | Default | How to change |
|-----------|---------|---------------|
| `MASSIVE_API_KEY` | `""` (use simulator) | Set in `.env` |
| `SimulatorDataSource.update_interval` | `0.5` seconds | Constructor arg |
| `SimulatorDataSource.event_probability` | `0.001` | Constructor arg |
| `MassiveDataSource.poll_interval` | `15.0` seconds | Constructor arg |
| `GBMSimulator.dt` | `0.5 / 5_896_800` ≈ 8.48e-8 | Constructor arg |
| SSE push cadence | `0.5` seconds | `_generate_events(interval=...)` |
| SSE client retry | `1000` ms | Hard-coded in `_generate_events` |

### Public package exports

```python
from app.market import (
    PriceUpdate,                 # models.py
    PriceCache,                  # cache.py
    MarketDataSource,            # interface.py
    create_market_data_source,   # factory.py
    create_stream_router,        # stream.py
)
```
