# FinAlly — Comprehensive Code Review

Date: 2026-06-12
Reviewer: Claude (team lead, post-build review)
Scope: All code produced for the platform build — database layer, services, REST/SSE API, LLM chat, Next.js frontend, scripts, and tests. The pre-existing market-data subsystem (`backend/app/market/`) was reviewed only at its integration boundary.

---

## 1. Executive Summary

The build is **functional, well-structured, and faithful to PLAN.md**. The codebase is clean, consistently typed, uses parameterized SQL throughout (no injection surface), shares a single validation path between REST and chat, and is backed by a real test pyramid that passes end-to-end.

**Verdict: Ship-ready for its stated purpose (a single-user local simulator), with a short list of correctness and production-hygiene items worth addressing.** None of the findings block local use; two (trade atomicity under concurrency, and the blocking LLM call) would matter under real load or with a real Groq key and should be scheduled.

### Verification performed for this review (not taken on trust)

| Check | Command | Result |
|---|---|---|
| Backend unit tests | `uv run --extra dev pytest` | **152 passed** |
| Backend lint | `uv run --extra dev ruff check app tests` | **All checks passed** |
| Frontend component tests | `npm test` (Jest) | **29 passed / 8 suites** (one teardown warning — see L4) |
| Full E2E gate | `test/run_e2e.ps1` | **25/25 passed (13.7s)** against a real clean build |

---

## 2. Architecture Assessment

The layering is sound and mostly one-directional:

```
api/ (routers)  ─┐
                 ├─> services/ (trades, portfolio, watchlist)  ─> db/ (repository) ─> SQLite
llm/ (chat)     ─┘                                              └─> market/ (PriceCache, source)
main.py wires everything; one shared PriceCache, one shared aiosqlite connection, one market source on app.state.
```

Strengths of the design:
- **Single validation path.** `services/trades.execute_trade` and `services/watchlist.execute_watchlist_change` are the only places trades/watchlist mutations are validated; both the REST routes and the LLM auto-execution call them. This was a deliberate consolidation and it paid off — REST and chat cannot diverge.
- **Source-agnostic market data.** The API neither knows nor cares whether prices come from the simulator or Massive.
- **Clean DI.** `api/deps.py` exposes the shared connection/cache/source from `app.state`; route handlers stay thin.
- **App factory + module-level `app`.** `create_app()` is testable; `app = create_app()` at module scope gives a stable `uvicorn app.main:app` entrypoint.

One layering smell is called out in M4.

---

## 3. Findings by Severity

### HIGH

#### H1 — Trade execution is not atomic and is subject to a lost-update race
`backend/app/services/trades.py:31`, `backend/app/db/repository.py` (every write commits independently)

`execute_trade` performs a read-modify-write on cash plus several independent writes, each committing separately on the **single shared connection**:

```
get_cash_balance (read) -> ... -> set_cash_balance (commit) -> upsert_position (commit)
-> insert_trade (commit) -> compute_total_value -> insert_snapshot (commit)
```

Two problems:
1. **No transaction boundary.** A failure (or process kill) between the cash debit and the position upsert leaves the books inconsistent (cash gone, no shares — or vice-versa on sell).
2. **Lost update / interleaving.** `aiosqlite` serializes individual statements, but the `await` points *between* statements let other coroutines run. The 30s snapshot loop, a manual trade, and a chat-driven trade can interleave. Because `commit()` is connection-global, one coroutine's commit flushes another's half-finished trade, and two concurrent buys can both read the same starting cash and double-spend.

In practice the blast radius is small (one human, fast requests), which is why tests pass. But the chat path can fire trades while the user clicks, so it is reachable.

**Recommendation:** wrap the whole order in one transaction and serialize orders. Cheapest robust fix: an `asyncio.Lock` held across `execute_trade`, plus doing the cash mutation as an atomic SQL update (`UPDATE users_profile SET cash_balance = cash_balance - ? WHERE ... AND cash_balance >= ?`) and committing once at the end instead of per-helper.

#### H2 — The LLM call is synchronous and blocks the event loop
`backend/app/llm/client.py:34` (`call_llm` uses blocking `litellm.completion`), invoked at `backend/app/llm/service.py:107` without `await`/executor.

In real (non-mock) mode, `completion(...)` is a blocking network call that can take seconds. It runs on the event loop thread, so for its entire duration **every other request in the process stalls — including the SSE price stream.** The "live Bloomberg terminal" prices freeze whenever the assistant is thinking. Mock mode hides this (no network), which is why the E2E suite is green.

**Recommendation:** switch to `litellm.acompletion` and `await` it (keep the tenacity retry as an async retry), or offload via `asyncio.to_thread(...)`. Low effort, removes a real UX regression under production keys.

### MEDIUM

#### M1 — Timestamps are not ISO-8601, deviating from the spec and shifting the P&L chart
`backend/app/db/schema.sql` (`DEFAULT (datetime('now'))` on every `*_at` column); surfaced raw by `repository.list_snapshots`/`list_trades` and `api/portfolio.get_history`.

SQLite `datetime('now')` yields `"2026-06-12 11:34:35"` (space separator, no `T`, no `Z`). PLAN.md §8 specifies ISO-8601 with a trailing `Z` (e.g. `"2026-01-01T10:00:00Z"`). Two consequences:
- **Contract deviation** for `recorded_at`/`executed_at` in API responses.
- **P&L chart axis is timezone-shifted.** `PnlChart.tsx:62` does `Date.parse(point.recorded_at)`; a string without a zone is parsed as **local time** by browsers, while the value is actually UTC. The curve shape is fine (all points shift equally) but absolute timestamps are wrong, and it is inconsistent with the SSE `timestamp` (which is proper ISO from the market layer).

**Recommendation:** store/emit ISO-8601 UTC — e.g. `strftime('%Y-%m-%dT%H:%M:%SZ','now')` in the schema defaults, or format in the repository on read.

#### M2 — Start script binds `0.0.0.0` and opens the browser before the server is up
`scripts/start_windows.ps1:32` (`--host 0.0.0.0`) and `:27` (browser opened before the blocking `uv run`).

- `0.0.0.0` exposes the trading UI **and the LLM-driven trade endpoint** to the whole local network. For a single-user local app this should be `127.0.0.1` (which is also what the E2E runner and `start_mac.sh` semantics expect — see the IPv4 note in PLAN §13).
- `Start-Process "http://localhost:8000"` runs *before* `uv run uvicorn` (which blocks), so the browser opens against a server that isn't listening yet; the user sees a connection error until they refresh.

**Recommendation:** bind `127.0.0.1`; start the server, poll `/api/health`, then open the browser (or print the URL and let the user click).

#### M3 — Chat history is not rehydrated in the UI
`frontend/src/lib/store.ts` (chat is in-memory only); no `GET /api/chat` history endpoint exists.

The backend faithfully persists every message to `chat_messages` and feeds the last 20 back to the model (`llm/service.py:101`). But the frontend keeps `chat` only in Zustand state. On reload the conversation pane is **empty while the model still remembers the prior turns** — a confusing asymmetry. PLAN.md doesn't mandate a history endpoint, so this is a product-consistency gap rather than a contract violation.

**Recommendation:** add `GET /api/chat/history` (reuse `list_recent_chat_messages`) and hydrate the store on load; or document that chat is intentionally ephemeral in the UI.

#### M4 — `llm` layer reaches up into the `api` layer
`backend/app/llm/service.py:28` — `from app.api.watchlist import get_watchlist as _build_watchlist`.

The chat context builder calls the **route handler** `get_watchlist` directly (it works only because the `Depends(...)` defaults are inert when called positionally). This inverts the intended dependency direction (`llm` → `api`) and couples the service to a FastAPI handler signature.

**Recommendation:** extract a `services/watchlist.build_watchlist_view(conn, cache)` and have both the route and the chat context call it.

### LOW / Nits

- **L1 — Falsy-price fallback.** `services/portfolio.py:25` `cache.get_price(ticker) or avg_cost` treats a legitimate `0.0` price as "missing." Stocks won't be 0, but prefer `price if price is not None else avg_cost`.
- **L2 — "/10" badge is not a real cap.** `Watchlist.tsx:99` shows `{n}/10`, implying a 10-ticker maximum that is enforced nowhere (backend and client both allow more). Either enforce it or drop the denominator.
- **L3 — Interactive element nested in a button.** `Watchlist.tsx:53` renders a `<span role="button">` (remove) inside the row `<button>`. Invalid HTML (a button may not contain interactive content) and an a11y nit; works only via `stopPropagation`. Make the row a `<div>` with an inner real button, or move remove outside.
- **L4 — Jest worker leak.** `npm test` reports "A worker process has failed to exit gracefully." Likely the `EventSource`/`setInterval` in `useLiveData` (or chart timers) not torn down in jsdom. Tests pass but this hints at a missing cleanup path; run with `--detectOpenHandles` and ensure effects clean up.
- **L5 — Minor redundancy/inefficiency.** `schema.TradeAction.quantity = Field(gt=0, ge=0.001)` is doubly constrained; `services/portfolio.compute_total_value` rebuilds the entire portfolio (re-querying cash + positions) just to return one number, and runs every 30s and after every trade.
- **L6 — Validation handler leaks internals.** `main.py:119` returns `"Invalid request: " + str(exc.errors())` — raw Pydantic error structures in the user-facing envelope. Fine for local, noisy for anything public.
- **L7 — Build-time font fetch.** `app/layout.tsx` uses `next/font/google`; an offline/air-gapped `npm run build` will fail fetching Space Grotesk / JetBrains Mono. Consider self-hosting the fonts for hermetic builds.
- **L8 — Playwright artifacts not ignored.** `.gitignore` covers `node_modules/`, `db/*.db`, `frontend/out/`, but not `test/test-results/` or `test/playwright-report/`, which a failed run will create.
- **L9 — E2E mutate the real DB.** The suite runs against the real `db/finally.db`; trade tests `reset` first, but watchlist add/remove persist across runs. Not isolated. Consider a `FINALLY_DB_PATH` env override so the runner points at a throwaway DB.
- **L10 — Fixed desktop grid.** `Dashboard.tsx:22` uses a fixed `260px_1fr_340px` grid with no breakpoint; below ~900px it overflows rather than degrading. PLAN only asks for "functional on tablet," so this is acceptable but noted.

---

## 4. Spec Conformance (PLAN.md §7–§9)

Faithfully implemented:
- **Schema** — all 6 tables, `user_id TEXT DEFAULT 'default'` everywhere, UNIQUE `(user_id,ticker)` on watchlist/positions, UUID TEXT PKs. ✔
- **Lazy init + WAL + idempotent seed** — `connection.py` (`PRAGMA journal_mode=WAL`, `CREATE IF NOT EXISTS`, `INSERT OR IGNORE`, $10k + 10 tickers). ✔
- **Error envelope** `{"ok": false, "error": ...}` with 400/404/500. ✔ (`errors.py`, handlers in `main.py`)
- **Watchlist response field names** — `prev_price`, `session_open`, `change_pct` (vs session_open). ✔ (`api/watchlist.py:37`)
- **Trade response shape** incl. `executed_at`, `cash_balance`. ✔
- **Reset** clears positions/trades/snapshots, restores $10k, preserves watchlist + chat. ✔ (`repository.reset_portfolio`)
- **Chat response shape** — `message`, `trades`, `watchlist_changes`, `trade_results`, `watchlist_results`. ✔ (`llm/service.handle_chat`)
- **Structured output schema** — `ChatResponse`/`TradeAction`/`WatchlistAction`, quantity min 0.001. ✔
- **System prompt** — "FinAlly, an AI trading assistant." ✔
- **Mock mode** — deterministic, no network, documented triggers. ✔ (`llm/mock.py`)

Deviations:
- **Timestamps not ISO-8601** (M1) — `recorded_at`/`executed_at` use SQLite's space-separated format vs the spec's `...Z`.

---

## 5. Security Review

This is a single-user local app with no auth **by design** (per PLAN.md), so the bar is "don't do anything reckless on localhost." Assessment:

- **SQL injection: none found.** Every query in `repository.py` is parameterized; tickers are additionally regex-validated (`watchlist.py:17`). ✔
- **Secrets:** `.env` is gitignored; `GROQ_API_KEY`/`MASSIVE_API_KEY` read from env; none hard-coded. ✔
- **Network exposure (M2):** `start_windows.ps1` binds `0.0.0.0`, exposing the app — including an endpoint where an LLM auto-executes trades — to the LAN. Recommend `127.0.0.1`.
- **LLM auto-execution of trades** is intentional and safe here (simulated money), but worth a one-line acknowledgement in docs that prompt-injected "buy" instructions would execute against the paper portfolio.
- **Error verbosity (L6):** validation handler echoes internal error structures. Harmless locally.
- **CORS:** none needed (single origin, static export served by the API). ✔

No high-severity security issues for the stated deployment model.

---

## 6. Component Notes

**Database (`app/db/`)** — Clean and minimal. Primitives are well-named and each commits its own write (which becomes a liability only under H1's concurrency). `list_recent_chat_messages` correctly fetches newest-N then reverses to chronological, with a `rowid` tie-break for same-second rows. `foreign_keys=ON` is set but the schema declares no FKs (harmless).

**Services (`app/services/`)** — The heart of the correctness story. `execute_trade` math is right (avg-cost recompute on buy, position removal when residual `< MIN_QUANTITY` on sell). See H1 for atomicity. `build_portfolio` is straightforward; note L1.

**API (`app/api/`)** — Thin, correct routers. The 404-vs-400 split for watchlist delete is handled by string-matching the error message (`watchlist.py:74`) — slightly brittle but adequate; a dedicated `NotFound` subclass would be cleaner.

**LLM (`app/llm/`)** — Good structure (schema/prompt/client/mock/service split). The mock's regex triggers are sensible and documented. Main issues: H2 (blocking call) and M4 (layering). History is loaded before the current user message is persisted, correctly avoiding a duplicate turn.

**Frontend (`frontend/`)** — Polished, idiomatic React 19 / Next 16. Highlights: Lightweight Charts time handling is **correct** (ms→seconds conversion and de-dupe-by-second keep the series strictly ascending — a common pitfall avoided in `MainChart.tsx:72` and `PnlChart.tsx:62`); `useFlash` cleanly times out the flash class; optimistic updates with REST resync after trades/chat. Nits L2/L3/L10. The store, formatting, and SSE wiring are clean.

**Scripts & tests** — Scripts are simple and correct aside from M2. The E2E suite is genuinely good: it asserts both UI and backend state, resets between trade tests, and exercises real SSE reconnection by aborting the stream route and waiting for `EventSource` to recover. Nits L8/L9.

---

## 7. Prioritized Action List

1. **(H2)** Make the LLM call async (`acompletion` + `await`) so chat doesn't freeze the SSE stream. *Low effort, real impact.*
2. **(H1)** Serialize + transactionally wrap `execute_trade`; do the cash debit as an atomic conditional SQL update. *Medium effort, correctness.*
3. **(M1)** Emit ISO-8601 UTC timestamps; fixes the contract and the P&L chart timezone shift. *Low effort.*
4. **(M2)** Bind `127.0.0.1` in `start_windows.ps1` and open the browser only after health is up. *Trivial.*
5. **(M3/M4)** Add a chat-history hydration endpoint; extract a `build_watchlist_view` service to remove the `llm → api` dependency. *Low effort.*
6. **(Nits)** L1, L3, L4, L8 as time permits.

---

## 8. Strengths Worth Preserving

- Single, shared validation path for trades and watchlist (REST == chat).
- Parameterized SQL everywhere; no injection surface.
- Correct, non-obvious Lightweight Charts time handling.
- Idempotent lazy DB init with WAL.
- Consistent error envelope and clean dependency injection.
- A real test pyramid that passes: 152 backend unit + 29 frontend component + 25 E2E, ruff clean.
- The IPv4/`localhost` health-gate fix (documented in PLAN §13) — a genuinely environment-dependent bug found and fixed during the build.
