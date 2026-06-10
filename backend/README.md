1	# FinAlly Backend
2	
3	FastAPI backend for the FinAlly AI Trading Workstation.
4	
5	## Structure
6	
7	- `app/` - Application code
8	  - `market/` - Market data subsystem
9	    - `models.py` - PriceUpdate dataclass
10	    - `cache.py` - Thread-safe price cache
11	    - `interface.py` - MarketDataSource abstract interface
12	    - `simulator.py` - GBM-based market simulator
13	    - `massive_client.py` - Massive/Polygon.io API client
14	    - `factory.py` - Data source factory
15	    - `stream.py` - SSE streaming endpoint
16	    - `seed_prices.py` - Default ticker prices and parameters
17	
18	- `tests/` - Unit and integration tests
19	  - `market/` - Market data tests
20	
21	## Running Tests
22	
23	```bash
24	# Install dependencies
25	uv sync --dev
26	
27	# Run all tests
28	uv run pytest
29	
30	# Run with coverage
31	uv run pytest --cov=app --cov-report=html
32	
33	# Run specific test file
34	uv run pytest tests/market/test_simulator.py
35	
36	# Run with verbose output
37	uv run pytest -v
38	```
39	
40	## Environment Variables
41	
42	- `MASSIVE_API_KEY` - Optional. If set, use real market data from Massive API. If not set, use the built-in simulator.
43	
44	## Development
45	
46	```bash
47	# Install dependencies
48	uv sync --dev
49	
50	# Run linter
51	uv run ruff check .
52	
53	# Format code
54	uv run ruff format .
55	```
56	