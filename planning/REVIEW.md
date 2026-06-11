# Review — Changes Since Last Commit

**HEAD:** `2d7a8df` — "Replace planning docs with comprehensive market data specifications"
**Branch:** `main`
**Review date:** 2026-06-11

---

## Summary

**4 files modified** (unstaged) since `2d7a8df`:

| Path | Status | Description |
|------|--------|-------------|
| `backend/app/market/cache.py` | Modified | Thread safety fix — `version` property now acquires `self._lock` |
| `backend/app/market/massive_client.py` | Modified | Idempotency guard in `start()` — prevents double-initialisation |
| `planning/MARKET_INTERFACE.md` | Modified | Three doc fixes: logging in `add_ticker`, `dt`/`event_prob` wiring in `SimulatorDataSource.start()`, module-level factory imports |
| `planning/PLAN.md` | Modified | Major editorial pass — condensed verbose sections, tightened schemas/examples, preserved all spec-critical information |

---

## Detailed Changes

### `backend/app/market/cache.py:76` — Thread Safety

`PriceCache.version` was reading `self._version` without the lock, unlike every other method in the class. Fixed by wrapping the read in `with self._lock:`.

**Impact**: Eliminates the only data-race potential in the cache. The `version` counter is used for SSE change detection — a stale read could cause an SSE tick to be missed or duplicated under rare concurrent access patterns.

### `backend/app/market/massive_client.py:42` — Start Idempotency

`MassiveDataSource.start()` now checks whether `self._task` is already running before creating a new `RESTClient` and spawning a second poll loop. Logs a warning and returns early if called redundantly.

**Impact**: Prevents duplicate background tasks and leaked `RESTClient` instances if `start()` is called while the source is already active.

### `planning/MARKET_INTERFACE.md` — Doc Corrections

1. **`MassiveDataSource.add_ticker()`** (line 288) — added `logger.info(...)` call matching the actual implementation in `massive_client.py`, so the planning doc inlines the latest code.

2. **`SimulatorDataSource.start()`** (line 368) — was a placeholder `self._sim = GBMSimulator(tickers=tickers, ...)`. Replaced with the real call that computes `dt` from `self._interval` and passes `event_probability`.

3. **Factory function** (line 395+) — moved `from .massive_client import MassiveDataSource` and `from .simulator import SimulatorDataSource` from lazy local imports to module-level. Reflects a deliberate style choice for this particular planning code snippet (actual source `factory.py` still uses lazy imports to avoid circular deps).

**Impact**: Planning docs stay in sync with actual implementation — no stale/incorrect code examples in `MARKET_INTERFACE.md`.

### `planning/PLAN.md` — Editorial Pass

Substantial reduction in redundancy without losing spec-significant content:

| What changed | Detail |
|---|---|
| **§1 Vision** | Trimmed "capstone project for an agentic AI coding course" backstory |
| **§2 UX** | Collapsed bullet lists from 1-line-per-item to compact inline form for watchlist, buy/sell, chart, etc. |
| **§3 Architecture** | Removed "Why These Choices" table and "Key Boundaries" prose — both obvious from file tree and stack description |
| **§5 Env vars** | Single-line `export MY_VAR=# comment` format instead of multi-line explanation blocks |
| **§6 Market Data** | Condensed prose, removed redundant "Simulator" / "Massive" subsections already detailed in dedicated planning docs |
| **§7 Database** | Compact schema: one-line-per-table with key fields inline; removed verbose descriptions of each column |
| **§8 API Endpoints** | Merged separate tables (Market Data, Portfolio, Watchlist, Chat, System) into a single endpoint table; collapsed JSON examples to one line where readable |
| **§9 LLM** | Shortened flow description, removed rate-limiting discussion (frontend disables button; sufficient for single-user demo) |
| **§10 Frontend** | Collapsed layout elements and tech notes into concise lists |
| **§11 Scripts** | Merged into one subsection with DB note |
| **§12 Testing** | Shortened strategies to one-liner per category |
| **§13 Build Status** | Kept module/tests table and remaining-components list; removed spec-conformance checklist (redundant with the three dedicated planning docs) and planning-doc-accuracy notes |

No spec-critical information was removed — wire field names (`prev_price`, `change_pct`), response shapes, schema columns, env vars, colour codes, and the remaining-work list are all preserved.

---

## Verdict

Two minor code improvements (thread safety, idempotency) and two documentation refinement passes. No new features, no regressions. The codebase is in a clean, stable state.
