1	# Backend — Developer Guide

## LLM Calls

Use the Groq skill to call LiteLLM with the `groq/openai/gpt-oss-120b` model via the Groq inference provider. Use Structured Outputs to parse results. The `GROQ_API_KEY` is in `.env` at the project root.
2	
3	## Project Setup
4	
5	```bash
6	cd backend
7	uv sync --extra dev   # Install all dependencies including test/lint tools
8	```
9	
10	## Market Data API
11	
12	The market data subsystem lives in `app/market/`. Use these imports:
13	
14	```python
15	from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source
16	```
17	
18	### Core Types
19	
20	- **`PriceUpdate`** — Immutable dataclass: `ticker`, `price`, `previous_price`, `timestamp`, plus properties `change`, `change_percent`, `direction` ("up"/"down"/"flat"), and `to_dict()` for JSON serialization.
21	
22	- **`PriceCache`** — Thread-safe in-memory store. Key methods:
23	  - `update(ticker, price, timestamp=None) -> PriceUpdate`
24	  - `get(ticker) -> PriceUpdate | None`
25	  - `get_price(ticker) -> float | None`
26	  - `get_all() -> dict[str, PriceUpdate]`
27	  - `remove(ticker)`
28	  - `version` property — monotonic counter, increments on every update (for SSE change detection)
29	
30	- **`MarketDataSource`** — Abstract interface implemented by `SimulatorDataSource` and `MassiveDataSource`. Lifecycle: `start(tickers)` -> `add_ticker()` / `remove_ticker()` -> `stop()`.
31	
32	- **`create_market_data_source(cache)`** — Factory. Returns `MassiveDataSource` if `MASSIVE_API_KEY` is set, otherwise `SimulatorDataSource`.
33	
34	### SSE Streaming
35	
36	```python
37	from app.market import create_stream_router
38	
39	router = create_stream_router(price_cache)  # Returns FastAPI APIRouter
40	# Endpoint: GET /api/stream/prices (text/event-stream)
41	```
42	
43	### Seed Data
44	
45	Default tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX. Seed prices and per-ticker volatility/drift params are in `app/market/seed_prices.py`.
46	
47	## Running Tests
48	
49	```bash
50	uv run --extra dev pytest -v              # All tests
51	uv run --extra dev pytest --cov=app       # With coverage
52	uv run --extra dev ruff check app/ tests/ # Lint
53	```
54	
55	## Demo
56	
57	```bash
58	uv run market_data_demo.py   # Live terminal dashboard with simulated prices
59	```
60	