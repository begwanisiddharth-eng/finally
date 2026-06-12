# FinAlly — Comprehensive Code Review (with remediation)

Date: 2026-06-12
Reviewer: Claude (team lead)
Scope: All code produced for the platform build — database layer, services, REST/SSE API, LLM chat, Next.js frontend, scripts, and tests. The pre-existing market-data subsystem (`backend/app/market/`) was reviewed only at its integration boundary.

This document records the original review **and** the remediation pass that followed it. Each finding carries a disposition (Fixed / Declined / Investigated) with the concrete change made.

---

## 1. Executive Summary

The build was functional, well-structured, and faithful to PLAN.md from the outset. A review surfaced two higher-severity correctness issues (trade atomicity under concurrency; a blocking LLM call) plus a set of medium/low items. **All accepted findings have been remediated**; two low items were deliberately declined with rationale, and one was investigated and found benign.

### Verification after remediation (re-run, not assumed)

| Check | Command | Result |
|---|---|---|
| Backend unit tests | `uv run --extra dev pytest` | **152 passed** |
| Backend lint | `uv run --extra dev ruff check app tests` | **All checks passed** |
| Frontend build | `npm run build` | **Compiled + static export OK** |
| Frontend component tests | `npm test` (Jest) | **29 passed / 8 suites** |
| Full E2E gate | `test/run_e2e.ps1` | **25/25 passed (~15s)** against a real clean build |

---

## 2. Disposition of Findings

| ID | Severity | Disposition | Summary of change |
|----|----------|-------------|-------------------|
| H1 | High | **Fixed** | Serialized trades/reset/snapshot under a shared `db_write_lock` |
| H2 | High | **Fixed** | LLM call is now async (`acompletion` + `await`) — no longer blocks the loop |
| M1 | Medium | **Fixed** | All timestamps emit ISO-8601 UTC (`...Z`) |
| M2 | Medium | **Fixed** | Start scripts bind `127.0.0.1`; browser opens only after health |
| M3 | Medium | **Fixed** | Added `GET /api/chat/history`; UI rehydrates chat on load |
| M4 | Medium | **Fixed** | Extracted `build_watchlist_view` service; removed `llm → api` import |
| L1 | Low | **Fixed** | Explicit `None` check instead of `or` fallback on price |
| L2 | Low | **Fixed** | Dropped the misleading `/10` watchlist badge |
| L3 | Low | **Fixed** | Watchlist row is no longer a button-in-button |
| L4 | Low | **Investigated → benign** | `--detectOpenHandles` reports no leak; in-band run is clean |
| L5 | Low | **Fixed (partial)** | Removed redundant constraint; left `compute_total_value` as-is |
| L6 | Low | **Fixed** | Validation handler summarizes failing fields, no internals |
| L7 | Low | **Declined** | Vendoring font binaries trades worse; build env has network |
| L8 | Low | **Fixed** | Playwright + throwaway-DB artifacts gitignored |
| L9 | Low | **Fixed** | E2E uses a throwaway DB via `FINALLY_DB_PATH` |
| L10 | Low | **Declined** | Fixed desktop grid is acceptable per PLAN ("functional on tablet") |

---

## 3. High Severity — Details

### H1 — Trade atomicity & lost-update race — **Fixed**
`backend/app/services/locks.py` (new), `backend/app/services/trades.py`, `backend/app/main.py`, `backend/app/api/portfolio.py`.

The app uses one shared aiosqlite connection whose `commit()` is connection-global, and `execute_trade` does a read-modify-write on cash across several `await` points. Concurrent trades (manual + chat) or a trade overlapping the 30s snapshot task could interleave and lose updates.

**Fix:** introduced a single `asyncio.Lock` (`db_write_lock`). `execute_trade` performs its whole order (cash, position, trade, snapshot, cash read) inside `async with db_write_lock`. The reset route and the snapshot loop take the same lock, so no multi-step write can interleave with another. This is the proportionate fix for a single-user app — it serializes the rare overlap without restructuring the repository or adding heavyweight transactions. (Per-statement commits remain; a full single-transaction rewrite was judged out of proportion to the risk and to the project's "keep it simple" mandate.)

### H2 — Synchronous LLM call blocked the event loop — **Fixed**
`backend/app/llm/client.py`, `backend/app/llm/service.py`, `backend/tests/llm/test_client.py`.

`call_llm` used blocking `litellm.completion` on the event-loop thread; in real (non-mock) mode this would freeze the SSE price stream for the whole process during each completion.

**Fix:** `completion_with_backoff` and `call_llm` are now `async` using `litellm.acompletion`; `service.handle_chat` awaits `call_llm`. The tenacity retry decorator applies to the async function unchanged. Tests updated to patch with coroutines; mock mode is unaffected.

---

## 4. Medium Severity — Details

### M1 — ISO-8601 timestamps — **Fixed**
`backend/app/db/schema.sql`, `backend/app/db/repository.py`.

All `*_at` defaults and the inline `updated_at` writes now use `strftime('%Y-%m-%dT%H:%M:%SZ','now')`, so `recorded_at`/`executed_at` match the PLAN §8 contract and the browser parses them as UTC (fixes the P&L chart's timezone shift). Backend tests assert presence only, so they remained green.

### M2 — Network bind & browser timing — **Fixed**
`scripts/start_windows.ps1`, `scripts/start_mac.sh`.

Both scripts now bind `--host 127.0.0.1` (was `0.0.0.0`, which exposed the trade endpoint to the LAN), start the server in the background, poll `/api/health`, open the browser only once healthy, then wait on the server process so Ctrl+C still stops it.

### M3 — Chat history rehydration — **Fixed**
`backend/app/api/chat.py`, `frontend/src/lib/{api,types,store,useLiveData}.ts`, `test/e2e/chat.spec.ts`.

Added `GET /api/chat/history` (reuses `list_recent_chat_messages`). The frontend fetches it once on load and maps each row to a UI message (executed `*_results` win over proposed actions), but only applies it if the user hasn't already started a conversation — so a slow fetch can't clobber a freshly sent message. The two chat UI E2E tests, which previously assumed a fresh empty panel (`toHaveCount(1)`), were updated to assert the **newest** bubbles for the turn, which is correct now that history persists.

### M4 — Layering (`llm` → `api`) — **Fixed**
`backend/app/services/watchlist.py`, `backend/app/api/watchlist.py`, `backend/app/llm/service.py`.

Extracted the price-shaped watchlist read into `services/watchlist.build_watchlist_view(conn, cache)`. The route and the chat context builder both call the service; `llm/service.py` no longer imports a FastAPI route handler.

---

## 5. Low Severity — Details

- **L1 — Fixed.** `services/portfolio.build_portfolio` now uses `cached_price if cached_price is not None else avg_cost` (no falsy-`0.0` trap).
- **L2 — Fixed.** Watchlist header shows the count without the misleading `/10` cap.
- **L3 — Fixed.** The watchlist row is now a `<div role="button">` with keyboard activation, and the remove control is a real `<button>` — valid HTML, no nested interactive content. Test ids unchanged; component + E2E tests pass.
- **L4 — Investigated; benign.** `npx jest --detectOpenHandles` reports **no** open handles and the in-band run shows no warning. The earlier "worker failed to exit gracefully" message is a `next/jest` + worker-pool teardown timing artifact, not a real leak. No code change made.
- **L5 — Fixed (partial).** Removed the redundant `gt=0` from `schema.TradeAction.quantity` (kept `ge=0.001`). `compute_total_value` rebuilding the portfolio was left as-is — the cost is negligible (runs every 30s / per trade) and inlining it would reduce clarity.
- **L6 — Fixed.** The `RequestValidationError` handler now returns `"Invalid request: check field(s): <names>"` instead of dumping raw Pydantic error structures.
- **L8 — Fixed.** `.gitignore` covers `test/test-results/`, `test/playwright-report/`, the SQLite WAL/shm sidecars, and the throwaway `test/e2e_finally.db*`.
- **L9 — Fixed.** `connection.db_path()` honors `FINALLY_DB_PATH`; both E2E runners point the backend at a throwaway DB and delete it (plus `-shm`/`-wal`) on teardown, so the suite never mutates the real `db/finally.db`. Verified: after a full E2E run, `db/` is untouched and no throwaway DB remains.

### Declined (with rationale)

- **L7 — build-time Google fonts.** `app/layout.tsx` uses `next/font/google`, so a fully offline build would fail fetching the fonts. Vendoring `.woff2` binaries into the repo to make builds hermetic trades one downside (network at build) for another (binary assets, manual font updates) and isn't warranted for this project; build environments here have network. CSS already falls back to `system-ui`/`ui-monospace`. Left as-is, documented.
- **L10 — fixed desktop grid.** `Dashboard` uses a fixed three-column grid with no breakpoint. PLAN only requires "desktop-first, functional on tablet," which it meets. Adding responsive breakpoints is polish beyond the spec; declined to keep scope tight.

---

## 6. Spec Conformance (PLAN.md §7–§9)

All previously-confirmed items still hold. The one prior deviation (non-ISO timestamps) is now resolved (M1). New surface: `GET /api/chat/history` is additive and documented in §8.

---

## 7. Security Review (post-fix)

- **SQL injection: none.** All queries parameterized; tickers regex-validated.
- **Network exposure:** resolved — start scripts bind `127.0.0.1` (M2).
- **Secrets:** `.env` gitignored; keys read from env; none hard-coded.
- **Error verbosity:** resolved — validation handler no longer leaks internals (L6).
- **LLM auto-execution** of trades remains intentional (simulated money). No high-severity issues for the single-user local deployment model.

---

## 8. Strengths Worth Preserving

- Single shared validation path for trades and watchlist (REST == chat), now joined by a shared watchlist read view.
- Parameterized SQL everywhere; no injection surface.
- Correct, non-obvious Lightweight Charts time handling (ms→seconds, de-dupe by second).
- Idempotent lazy DB init with WAL; now with an env-overridable path for safe testing.
- Consistent error envelope and clean dependency injection.
- A real test pyramid that passes after remediation: **152 backend + 29 frontend + 25 E2E, ruff clean**.
- Concurrency-safe trade path and a non-blocking async LLM call added during remediation.

---

## 9. Residual Notes (not defects)

- `execute_trade` still commits per statement under the lock; the lock prevents interleaving, but a hard process kill mid-order could in principle leave a partially-applied trade. Acceptable for a local single-user simulator; a single-transaction rewrite is the path if this ever becomes multi-user.
- Chat history rehydration applies only when the panel is empty on load (by design, to avoid clobbering in-flight messages).
