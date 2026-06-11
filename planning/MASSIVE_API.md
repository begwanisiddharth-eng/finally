# Massive API Reference (formerly Polygon.io)

Reference documentation for the Massive (formerly Polygon.io) REST API as used in FinAlly.

## Overview

Polygon.io rebranded as **Massive.com** on October 30, 2025. Existing API keys, accounts, and
integrations continue to work as before. The Python package name changed to `massive` and the
default base URL is now `api.massive.com`; `api.polygon.io` remains supported.

- **Python package**: `massive` (`uv add massive`)
- **Min Python**: 3.9+
- **Auth**: API key passed to `RESTClient(api_key=...)` or read from `MASSIVE_API_KEY` env var
- **Auth header**: `Authorization: Bearer <API_KEY>` (handled automatically by the client)
- **Legacy package alias**: `polygon-api-client` (still installable, installs the same library)

## Rate Limits

| Tier | Limit | Recommended poll interval |
|------|-------|--------------------------|
| Free | 5 requests/minute | 15 seconds |
| Paid (all tiers) | Effectively unlimited | 2–5 seconds |

FinAlly polls all tickers in a single API call per interval, so rate limit consumption is
1 request per poll cycle regardless of watchlist size.

## Client Initialization

```python
from massive import RESTClient

# Reads MASSIVE_API_KEY from environment automatically
client = RESTClient()

# Or pass the key explicitly
client = RESTClient(api_key="your_key_here")

# Debug mode — logs request URLs and response headers
client = RESTClient(api_key="your_key_here", trace=True, verbose=True)
```

The client is **synchronous**. In an async FastAPI context, wrap calls in
`asyncio.to_thread()` to avoid blocking the event loop (see FinAlly usage below).

## Method Naming Conventions

- **`get_*` methods** — return a single object directly (no pagination)
- **`list_*` methods** — return a lazy iterator that auto-paginates through all results

---

## Endpoints Used in FinAlly

### 1. Snapshot — All Tickers (Primary Polling Endpoint)

Fetches current prices for multiple tickers in **one API call**. This is the main endpoint
used by `MassiveDataSource` for its polling loop.

**REST (v2)**: `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT`

**Python client (v2)**:
```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient()

snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
)

for snap in snapshots:
    price = snap.last_trade.price
    ts_ms = snap.last_trade.timestamp       # Unix milliseconds
    ts_sec = snap.last_trade.timestamp / 1000.0

    print(f"{snap.ticker}: ${price:.2f}")
    print(f"  Day change: {snap.day.change_percent:.2f}%")
    print(f"  Day OHLCV: O={snap.day.open} H={snap.day.high} L={snap.day.low} C={snap.day.close} V={snap.day.volume}")
    print(f"  Prev close: {snap.day.previous_close}")
```

**v2 Response fields per snapshot**:

| Field path | Type | Description |
|---|---|---|
| `ticker` | str | Ticker symbol |
| `last_trade.price` | float | Most recent trade price |
| `last_trade.timestamp` | int | Trade time, Unix **milliseconds** |
| `last_trade.size` | int | Trade size (shares) |
| `last_trade.exchange` | int | Exchange ID |
| `last_quote.bid_price` | float | Best bid |
| `last_quote.ask_price` | float | Best ask |
| `last_quote.bid_size` | int | Bid size |
| `last_quote.ask_size` | int | Ask size |
| `day.open` | float | Day open |
| `day.high` | float | Day high |
| `day.low` | float | Day low |
| `day.close` | float | Day close (latest) |
| `day.volume` | int | Day volume |
| `day.vwap` | float | Day volume-weighted average price |
| `day.previous_close` | float | Previous session close |
| `day.change` | float | Absolute change from previous close |
| `day.change_percent` | float | Percentage change from previous close |

**Key fields FinAlly extracts**: `last_trade.price` (for the cache) and
`last_trade.timestamp` (converted from ms to seconds for `PriceCache.update()`).

---

### 2. Unified Snapshot — v3 (Newer Multi-Asset Endpoint)

The v3 unified snapshot endpoint consolidates stocks, options, forex, and crypto in one
call. For stocks only, filter by `type=stocks`. This is the recommended endpoint for new
integrations; v2 snapshots remain available.

**REST (v3)**: `GET /v3/snapshot?ticker.any_of=AAPL,MSFT&type=stocks&limit=250`

**Python client (v3)**:
```python
snapshots = list(client.list_universal_snapshots(
    params={
        "ticker.any_of": "AAPL,GOOGL,MSFT",
        "type": "stocks",
    }
))

for snap in snapshots:
    price = snap.last_trade.price
    ts_ns = snap.last_trade.last_updated    # Unix nanoseconds in v3
    ts_sec = ts_ns / 1_000_000_000.0

    print(f"{snap.ticker}: ${price:.2f}")
    print(f"  Session change: {snap.session.change_percent:.2f}%")
    print(f"  Market status: {snap.market_status}")  # open/closed/early_trading/late_trading
```

**v3 Response shape** (per result in `results` array):

```json
{
  "ticker": "AAPL",
  "type": "stocks",
  "name": "Apple Inc.",
  "market_status": "closed",
  "last_trade": {
    "price": 195.50,
    "size": 2,
    "exchange": 316,
    "last_updated": 1675280958783136800,
    "timeframe": "REAL-TIME"
  },
  "last_quote": {
    "ask": 195.52,
    "ask_size": 110,
    "bid": 195.49,
    "bid_size": 172,
    "last_updated": 1675280958756383500,
    "timeframe": "REAL-TIME"
  },
  "last_minute": {
    "open": 195.40,
    "high": 195.55,
    "low": 195.38,
    "close": 195.50,
    "volume": 610,
    "vwap": 195.47,
    "transactions": 26
  },
  "session": {
    "open": 190.00,
    "high": 196.10,
    "low": 189.50,
    "close": 195.50,
    "volume": 45000000,
    "change": 5.50,
    "change_percent": 2.90,
    "previous_close": 190.00,
    "early_trading_change": -0.30,
    "early_trading_change_percent": -0.16,
    "late_trading_change": 1.20,
    "late_trading_change_percent": 0.61
  }
}
```

**v2 vs v3 comparison**:

| Aspect | v2 (`get_snapshot_all`) | v3 (`list_universal_snapshots`) |
|---|---|---|
| Endpoint | `/v2/snapshot/locale/us/markets/stocks/tickers` | `/v3/snapshot` |
| Day data field | `snap.day.*` | `snap.session.*` |
| Timestamp | `last_trade.timestamp` (ms) | `last_trade.last_updated` (ns) |
| Multi-asset | Stocks only | Stocks, options, forex, crypto, indices |
| Return type | List | Lazy iterator (auto-paginates) |
| Pagination limit | n/a | Up to 250 tickers per request |

**FinAlly uses v2** (`get_snapshot_all`) because it returns all requested tickers in a
single non-paginated response, which is simpler for a polling use case with a small watchlist.

---

### 3. Single Ticker Snapshot

Detailed snapshot for one ticker. Useful for a ticker detail view.

```python
snapshot = client.get_snapshot_ticker(
    market_type=SnapshotMarketType.STOCKS,
    ticker="AAPL",
)

print(f"Price: ${snapshot.last_trade.price}")
print(f"Bid/Ask: ${snapshot.last_quote.bid_price} / ${snapshot.last_quote.ask_price}")
print(f"Day range: ${snapshot.day.low} – ${snapshot.day.high}")
print(f"Day change: {snapshot.day.change_percent:.2f}%")
```

---

### 4. Previous Close

Previous trading session OHLCV for a ticker. Useful for seeding initial prices.

**REST**: `GET /v2/aggs/ticker/{ticker}/prev`

```python
results = client.get_previous_close_agg(ticker="AAPL")

for agg in results:
    print(f"Prev close: ${agg.close}")
    print(f"OHLCV: O={agg.open} H={agg.high} L={agg.low} C={agg.close} V={agg.volume}")
    print(f"Timestamp: {agg.timestamp}")  # Unix milliseconds (start of session)
```

---

### 5. Aggregates (Bars)

Historical OHLCV bars. Used for historical chart display (not required for FinAlly's
live dashboard, but available for future chart history features).

**REST**: `GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}`

```python
aggs = []
for agg in client.list_aggs(
    ticker="AAPL",
    multiplier=1,
    timespan="day",         # "minute", "hour", "day", "week", "month", "quarter", "year"
    from_="2025-01-01",
    to="2025-06-01",
    limit=50000,            # page size; auto-paginates
):
    aggs.append(agg)

for agg in aggs:
    print(f"t={agg.timestamp}, O={agg.open} H={agg.high} L={agg.low} C={agg.close} V={agg.volume}")
```

Response fields per bar: `timestamp` (Unix ms, bar open), `open`, `high`, `low`, `close`,
`volume`, `vwap`, `transactions`.

---

### 6. Last Trade

Most recent trade for a single ticker.

```python
trade = client.get_last_trade(ticker="AAPL")
print(f"Price: ${trade.price}, Size: {trade.size}")
print(f"Exchange: {trade.exchange}, Timestamp: {trade.participant_timestamp}")
```

---

### 7. Last Quote (NBBO)

Most recent National Best Bid/Offer.

```python
quote = client.get_last_quote(ticker="AAPL")
print(f"Bid: ${quote.bid} x {quote.bid_size}")
print(f"Ask: ${quote.ask} x {quote.ask_size}")
```

---

## How FinAlly Uses the API

`MassiveDataSource` runs as a background asyncio task:

1. Collects all tickers from its internal list (synced from the watchlist)
2. Calls `get_snapshot_all()` for all tickers in **one API call**
3. Extracts `last_trade.price` and `last_trade.timestamp` from each snapshot
4. Writes results to the shared `PriceCache`
5. Sleeps for the poll interval, then repeats

Because `RESTClient` is synchronous, the poll call is dispatched to a thread pool via
`asyncio.to_thread()` so the FastAPI event loop is never blocked:

```python
import asyncio
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

from .cache import PriceCache


async def poll_once(client: RESTClient, tickers: list[str], cache: PriceCache) -> None:
    """Fetch snapshots for all tickers and update the cache."""
    def fetch() -> list:
        return client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=tickers,
        )

    snapshots = await asyncio.to_thread(fetch)

    for snap in snapshots:
        try:
            price = snap.last_trade.price
            timestamp = snap.last_trade.timestamp / 1000.0  # ms → seconds
            cache.update(ticker=snap.ticker, price=price, timestamp=timestamp)
        except (AttributeError, TypeError):
            pass  # Skip malformed snapshots; next poll will retry


async def poll_loop(api_key: str, get_tickers, cache: PriceCache, interval: float = 15.0) -> None:
    """Background polling loop."""
    client = RESTClient(api_key=api_key)

    # Immediate first poll so the cache has data right away
    await poll_once(client, get_tickers(), cache)

    while True:
        await asyncio.sleep(interval)
        tickers = get_tickers()
        if tickers:
            await poll_once(client, tickers, cache)
```

---

## Error Handling

The client raises exceptions for HTTP errors. FinAlly catches them in the poll loop and
logs the error without crashing — the loop retries on the next interval.

| HTTP Status | Cause | Action |
|---|---|---|
| 401 | Invalid API key | Log and retry (key may be rotated) |
| 403 | Plan doesn't include endpoint | Log; check subscription tier |
| 429 | Rate limit exceeded | Log; increase `poll_interval` |
| 5xx | Server error | Log; built-in client retry (3 attempts) |

```python
try:
    snapshots = await asyncio.to_thread(fetch)
except Exception as e:
    logger.error("Massive poll failed: %s", e)
    # Don't re-raise — the loop continues on next interval
```

---

## Behavior Notes

- **Single API call for all tickers** — critical for staying within the 5 req/min free tier limit
- **Timestamps are Unix milliseconds** in v2 responses; divide by 1000 for seconds
- **Market hours**: `last_trade.price` reflects the last traded price whether the market is
  open, in pre/post-market, or closed. The `day` object resets at market open.
- **After-hours data**: present in v3 `session` fields (`early_trading_change`,
  `late_trading_change`, etc.)
- **Unknown tickers**: the API does not validate tickers; a request for a non-existent symbol
  simply returns no snapshot entry for that ticker (or an error entry in v3)
- **Free tier is enough for FinAlly demo** at 15-second polling; paid tier is needed for
  near-real-time updates (2–5 second polling)
