# Backend -- Developer Guide

## LLM Calls

Use the Groq skill to call LiteLLM with the `groq/openai/gpt-oss-120b` model via the Groq inference provider. Use Structured Outputs to parse results. The `GROQ_API_KEY` is in `.env` at the project root.

## Project Setup

```bash
cd backend
uv sync --extra dev   # Install all dependencies including test/lint tools
```

## Market Data API

The market data subsystem lives in `app/market/`. Use these imports:

```python
from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source
```

### Core Types

- **`PriceUpdate`** -- Immutable dataclass: `ticker`, `price`, `previous_price`, `timestamp`, plus properties `change`, `change_percent`, `direction` ("up"/"down"/"flat"), and `to_dict(session_open=None)` for JSON serialization. `to_dict()` outputs spec wire field names: `prev_price`, `change_pct`, ISO 8601 `timestamp`.

- **`PriceCache`** -- Thread-safe in-memory store. Key methods:
  - `update(ticker, price, timestamp=None) -> PriceUpdate`
  - `get(ticker) -> PriceUpdate | None`
  - `get_price(ticker) -> float | None`
  - `get_all() -> dict[str, PriceUpdate]`
  - `get_session_open(ticker) -> float | None`
  - `remove(ticker)`
  - `version` property -- monotonic counter, increments on every update (for SSE change detection)

- **`MarketDataSource`** -- Abstract interface implemented by `SimulatorDataSource` and `MassiveDataSource`. Lifecycle: `start(tickers)` -> `add_ticker()` / `remove_ticker()` -> `stop()`.

- **`create_market_data_source(cache)`** -- Factory. Returns `MassiveDataSource` if `MASSIVE_API_KEY` is set, otherwise `SimulatorDataSource`.

### SSE Streaming

```python
from app.market import create_stream_router

router = create_stream_router(price_cache)  # Returns FastAPI APIRouter
# Endpoint: GET /api/stream/prices (text/event-stream)
# Emits one JSON event per ticker per ~500ms: {ticker, price, prev_price, session_open, change_pct, direction, timestamp}
```

### Seed Data

Default tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX. Seed prices and per-ticker volatility/drift params are in `app/market/seed_prices.py`.

## Running Tests

```bash
uv run --extra dev pytest -v              # All tests
uv run --extra dev pytest --cov=app       # With coverage
uv run --extra dev ruff check app/ tests/ # Lint
```

## Demo

```bash
uv run market_data_demo.py   # Live terminal dashboard with simulated prices
```
