# Code Review — FinAlly Market Data Backend

**Scope:** `backend/app/market/` (8 modules), `backend/tests/market/` (6 test modules), `backend/pyproject.toml`, `backend/tests/conftest.py`, project-level files.

**Summary:** The market data subsystem is well-structured and functionally solid. The GBM math is correct, the abstraction layers are clean, and the test coverage is good. There are several deviations from the spec that will require attention before the frontend and remaining backend components can be built on top of this, plus a few correctness issues in the existing code.

---

## 1. Spec Deviations (must fix before downstream work)

### 1.1 SSE event shape does not match the spec

**Severity: Blocking for frontend integration.**

The spec defines the SSE event as a per-ticker object:
```json
{"ticker": "AAPL", "price": 195.50, "prev_price": 194.20, "session_open": 190.00, "change_pct": 2.89, "direction": "up", "timestamp": "2026-01-01T10:00:00Z"}
```

The implementation in `stream.py` (line 81) sends a batch dict-of-dicts:
```json
{"AAPL": {"ticker": "AAPL", "price": ..., "previous_price": ..., "change_percent": ...}, "GOOGL": {...}}
```

Three concrete differences:

- **Event structure**: spec = one ticker per `data:` line; implementation = all tickers in one `data:` line. The frontend `EventSource` handler will need to know which format to expect. A single batch event is actually reasonable and arguably better for the watchlist use case, but it must match what the frontend will be built to consume. This should be decided and documented as the contract.

- **Field names**: `prev_price` and `change_pct` (spec) vs `previous_price` and `change_percent` (implementation). The `GET /api/watchlist` response also uses `prev_price` and `change_pct`. Whatever names are chosen must be consistent across SSE and the REST endpoints.

- **`session_open` is missing entirely.** Neither `PriceUpdate`, `PriceCache`, nor `stream.py` tracks session-open price. The spec requires this field in both the SSE event and `GET /api/watchlist`. The cache will need a separate `_session_open` dict populated on first update per ticker per process lifetime. This is a moderate addition.

- **Timestamp format**: spec uses ISO 8601 string (`"2026-01-01T10:00:00Z"`); implementation uses Unix float. The frontend will parse one or the other; this must match.

### 1.2 `PriceCache` does not track `session_open`

Related to 1.1. The spec states: "The cache holds per ticker: latest price, previous price, session-open price (price at first observation this session), and timestamp." The `PriceCache` class tracks only latest price (and implicitly previous via `PriceUpdate`). A `_session_open: dict[str, float]` needs to be added with a corresponding `get_session_open(ticker)` method.

---

## 2. Correctness Issues

### 2.1 `timestamp or time.time()` is falsy for `timestamp=0.0`

**File:** `backend/app/market/cache.py`, line 30.

```python
ts = timestamp or time.time()
```

`0.0` is falsy in Python, so any caller passing `timestamp=0.0` (a valid Unix epoch value) would silently get `time.time()` instead. This should be:

```python
ts = timestamp if timestamp is not None else time.time()
```

The `MassiveDataSource` converts milliseconds to seconds on line 103 of `massive_client.py`; it is unlikely to produce `0.0`, but the defensive fix is still correct.

### 2.2 `version` property is read outside the lock

**File:** `backend/app/market/cache.py`, lines 65–67.

```python
@property
def version(self) -> int:
    return self._version
```

`self._version` is incremented inside `update()` while holding `self._lock`, but the `version` property reads it without the lock. In CPython this is safe in practice due to the GIL and the atomic nature of integer reads, but it is technically a data race. Since this is read-only by the SSE loop and only incremented by the writer, the practical impact is zero. Mentioned for completeness; acceptable to leave as-is with a comment.

### 2.3 GBM `dt` is hardcoded and decoupled from `update_interval`

**File:** `backend/app/market/simulator.py`, lines 48 and 220–223.

`GBMSimulator.DEFAULT_DT` is fixed at `0.5 / TRADING_SECONDS_PER_YEAR`. `SimulatorDataSource` accepts an `update_interval` parameter (default `0.5`) but never passes it to `GBMSimulator` as `dt`. If someone instantiates `SimulatorDataSource(price_cache=cache, update_interval=1.0)`, the time step stays at 500ms-equivalent, halving the simulated price variance per actual second. For the default case of `0.5s` this is correct, but it is a latent inconsistency. `SimulatorDataSource.start()` should compute and pass `dt = self._interval / GBMSimulator.TRADING_SECONDS_PER_YEAR`.

### 2.4 `stream.py` module-level router mutated by factory

**File:** `backend/app/market/stream.py`, lines 17–48.

```python
router = APIRouter(prefix="/api/stream", tags=["streaming"])  # module-level

def create_stream_router(price_cache: PriceCache) -> APIRouter:
    @router.get("/prices")           # decorates the MODULE-LEVEL router
    async def stream_prices(...):
        ...
    return router
```

`create_stream_router()` is meant to be a factory, but it registers the route on a shared module-level `router` object. If called a second time (e.g., in tests that import the function), the route `/prices` would be registered twice on the same router, which FastAPI may silently accept, causing undefined behavior. The fix is to create the `APIRouter` inside the factory function:

```python
def create_stream_router(price_cache: PriceCache) -> APIRouter:
    router = APIRouter(prefix="/api/stream", tags=["streaming"])
    @router.get("/prices")
    async def stream_prices(...):
        ...
    return router
```

---

## 3. Missing Application Infrastructure

These are not bugs in the completed market data component, but they will block the next agent from building on it.

### 3.1 No FastAPI app entry point

There is no `backend/app/main.py` (or equivalent). No `FastAPI()` instance, no lifespan handler to call `source.start()` and `source.stop()`, no static file mount, no router registration. The downstream Backend Engineer agent will need to create this. The market data component is ready to be plugged in but cannot run as-is.

### 3.2 Missing core dependencies in `pyproject.toml`

The following packages are required by the spec but absent from `dependencies`:

- `python-dotenv` — needed to load `.env` at startup. Currently arrives as a transitive dependency of `uvicorn[standard]` and would break if `uvicorn` drops it. It should be declared explicitly.
- `litellm` — required for LLM integration (§9 of spec).
- An async SQLite driver — `aiosqlite` is the standard choice for async FastAPI + SQLite. The spec requires database access from async route handlers.

### 3.3 Missing project scaffolding

The following are called out by the spec but do not exist yet:

- `frontend/` — Next.js project
- `scripts/start_mac.sh`, `scripts/start_windows.ps1`, and stop equivalents
- `test/run_e2e.sh` / `test/run_e2e.ps1`
- `db/.gitkeep` — the `db/` directory for the SQLite file
- `.env.example` — the spec says this should be committed; the actual `.env` is (correctly) gitignored

### 3.4 `db/finally.db` is not gitignored

The `.gitignore` covers `db.sqlite3` (a Django convention) but does NOT cover `db/finally.db`, which is the path the spec mandates. When the database is created at runtime, it will appear as an untracked file. Add `db/finally.db` or `db/*.db` to `.gitignore`.

---

## 4. Code Quality Issues

### 4.1 `uv sync --dev` in README is wrong

**File:** `backend/README.md`, lines 25 and 48.

`uv sync --dev` is not a valid `uv` flag (`--dev` is a pip/poetry-ism). The correct command is `uv sync --extra dev`, which matches `backend/CLAUDE.md`. All documentation and scripts that reference this command should use `--extra dev`.

### 4.2 `conftest.py` `event_loop_policy` fixture does nothing

**File:** `backend/tests/conftest.py`.

The fixture returns `asyncio.DefaultEventLoopPolicy()` but never calls `asyncio.set_event_loop_policy()`. The return value of a non-yield pytest fixture that is not explicitly requested by a test does nothing. In `pytest-asyncio >= 0.21`, event loop configuration is done via `asyncio_mode` in `pyproject.toml` (already set to `"auto"`) or via `@pytest.mark.asyncio(loop_scope=...)`. This fixture is dead code and should be removed.

### 4.3 `MassiveDataSource.start()` does not normalize tickers

**File:** `backend/app/market/massive_client.py`.

`add_ticker()` and `remove_ticker()` both call `.upper().strip()` on the ticker argument, but `start(tickers: list[str])` does not. If the caller passes lowercase tickers to `start()`, they will be stored as-is and will not match the normalized versions returned from `add_ticker()`. `start()` should normalize: `self._tickers = [t.upper().strip() for t in tickers]`.

### 4.4 `.env` contains an `OPENAI_API_KEY`

**File:** `.env` (gitignored, but present on disk).

The `.env` file contains `OPENAI_API_KEY` which is not mentioned in the spec and not used by the backend. The spec specifies only `GROQ_API_KEY`, `MASSIVE_API_KEY`, and `LLM_MOCK`. This key should be removed. More importantly, the `.env.example` file referenced in the README (`cp .env.example .env`) does not exist — it needs to be created containing only the three spec-defined variables with placeholder values.

---

## 5. Minor / Informational

- **`PriceUpdate.change` rounds to 4 decimal places** but `PriceCache.update()` rounds prices to 2 decimal places before storing. The `change` property computes from already-rounded values, so the 4-decimal rounding on `change` is cosmetic noise. Rounding `change` to 2 is more consistent with a financial display context.

- **`GBMSimulator._tickers` is a list (not a set)**, so `ticker in self._prices` guard in `_add_ticker_internal` is correct (O(1) dict lookup), but `self._tickers.remove(ticker)` in `remove_ticker` is O(n). For n < 50 this is irrelevant.

- **`test_simulator.py` line 48 accesses `sim._tickers` directly** in `test_add_duplicate_is_noop`, testing a private attribute. Prefer `sim.get_tickers()`.

- **`backend/README.md` says `uv sync --dev`** in two places (see §4.1); `backend/CLAUDE.md` correctly says `uv sync --extra dev`.

- **The `rich` dependency** is listed in `dependencies` (not `dev`), which means it ships with the production backend. It is only used by `market_data_demo.py` (a development tool). Moving it to `optional-dependencies.dev` would keep the production install leaner.

---

## Summary Table

| # | Issue | Severity | File |
|---|-------|----------|------|
| 1.1 | SSE event shape, field names, and batch-vs-per-ticker diverge from spec | Blocking | `stream.py`, `models.py` |
| 1.2 | `session_open` not tracked in cache or emitted in SSE | Blocking | `cache.py`, `models.py`, `stream.py` |
| 2.1 | `timestamp=0.0` treated as falsy | Bug | `cache.py:30` |
| 2.2 | `version` read outside lock | Minor / GIL-safe | `cache.py:66` |
| 2.3 | GBM `dt` not derived from `update_interval` | Latent bug | `simulator.py:220` |
| 2.4 | `create_stream_router` mutates module-level router | Bug (test/re-use risk) | `stream.py:17` |
| 3.1 | No FastAPI app entry point | Blocks next phase | — |
| 3.2 | `python-dotenv`, `litellm`, `aiosqlite` missing from deps | Blocks next phase | `pyproject.toml` |
| 3.3 | `frontend/`, `scripts/`, `test/`, `db/`, `.env.example` missing | Blocks next phase | project root |
| 3.4 | `db/finally.db` not gitignored | Housekeeping | `.gitignore` |
| 4.1 | `uv sync --dev` is wrong flag | Documentation bug | `backend/README.md` |
| 4.2 | `event_loop_policy` fixture is dead code | Cleanup | `tests/conftest.py` |
| 4.3 | `start()` in `MassiveDataSource` does not normalize tickers | Bug | `massive_client.py:43` |
| 4.4 | `.env` has `OPENAI_API_KEY`; `.env.example` missing | Cleanup / correctness | `.env` |
