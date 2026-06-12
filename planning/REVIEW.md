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

---

## 10. Review of the Remediation Commit (9a389b0)

The latest commit merged the `review-fixes` branch, closing items H1, H2, M1-M4, and L1-L6/L8-L9 from the original review. This section reviews the remediation code itself.

### Assessment

The fixes are correct and proportionate. The approach is consistently pragmatic — lock-based serialization rather than full transactions, async migration for the LLM call, extracted services rather than architectural rewrites. All accepted findings were properly resolved.

### Issues found in the remediation code

| ID | Severity | File | Finding |
|----|----------|------|---------|
| R1 | **High** | `frontend/src/lib/useLiveData.ts:38` | **Uncaught `JSON.parse` in SSE handler.** A malformed SSE event throws `SyntaxError` inside the `onmessage` callback, which then triggers `source.onerror` and sets the connection status to `"disconnected"`. React's commit phase could also crash depending on the error boundary. Wrap in `try/catch` with a `console.warn` and skip the event. |
| R2 | **Medium** | `frontend/src/lib/api.ts:18` | **`res.json()` crashes on non-JSON responses.** If the backend returns an HTML error page (reverse proxy, 502, etc.), `res.json()` throws `SyntaxError` as an unhandled promise rejection. Wrap in `try/catch` and fall back to `res.text()`. |
| R3 | **Medium** | `backend/app/llm/service.py:112-119` | **LLM loses execution feedback.** The assistant message content is persisted verbatim from the LLM, but execution results (`trade_results`, `watchlist_results`) are stored separately in the `actions` column. On the next chat turn, `prompt.py` feeds only `role` and `content` to the LLM — it never sees that its proposed trade actually failed (e.g., insufficient cash). The model builds subsequent decisions on a false premise. Append failure/success context to the assistant message content, or pass `actions` in the history assembly. |
| R4 | **Medium** | `backend/app/llm/client.py:46` | **No guard against empty `choices`.** If the LLM returns `choices: []` (possible during API degradation), `response.choices[0]` raises `IndexError` and crashes the chat endpoint with a 500. Check `if not response.choices` and raise a descriptive `LLMError`. |
| R5 | **Medium** | `backend/app/services/trades.py:62-71` | **`GET /api/portfolio` can observe an inconsistent state.** The trade path is serialized under `db_write_lock`, but `build_portfolio` does NOT acquire it. Between cash debit and position upsert, a concurrent portfolio read sees cash spent but no position yet. Either acquire the read lock in `build_portfolio` or make the two writes atomic. |
| R6 | **Medium** | `backend/app/services/watchlist.py:34` | **`session_open` falsy-zero trap.** `if price is not None and session_open` treats `session_open=0.0` as falsy, so `change_pct` defaults to `0.0`. Should be `session_open is not None` to match the fix in L1 for prices. |
| R7 | **Medium** | `frontend/src/lib/store.ts:88` | **SSE auto-select overrides explicit deselection.** `selectedTicker: state.selectedTicker ?? event.ticker` re-selects a ticker on every SSE event if the user has never clicked one, and also re-selects if the user explicitly set it to `null`. Use a sentinel (e.g., `__never__`) to distinguish "never selected" from "deselected." |
| R8 | **Medium** | `backend/app/db/connection.py:55-65` | **Seed data has no validation.** Hard-coded seed tickers (`SEED_TICKERS`) are inserted via `INSERT OR IGNORE` — invalid tickers fail silently with no warning. Add a startup log if any seed insert is skipped. |
| R9 | **Low** | `frontend/src/lib/useLiveData.ts:57-77` | **Stale-data race in periodic pull.** `pull()` is called immediately plus every 5s via `setInterval`. If a pull takes >5s, completions can overwrite newer data with stale data. Use a flag or serial queue to ignore stale completions. |
| R10 | **Low** | `frontend/src/components/Watchlist.tsx:24-28` | **`onRemove` bypasses the store action.** The handler calls `useStore.setState` directly with an inline filter instead of using `setWatchlist`. If the watchlist state shape ever changes, this inlined mutation becomes a maintenance trap. Standardise on the store action. |
| R11 | **Low** | `frontend/src/lib/useLiveData.ts:25-30` | **Six separate Zustand selectors.** Each `useStore(s => s.xxx)` is an independent subscription. A single selector with shallow comparison would reduce subscription overhead. |
| R12 | **Low** | `backend/app/main.py:108` | **Silent `ImportError` swallow.** `_include_chat_router` catches `ImportError` without logging. A missing dependency or syntax error in the chat module goes undiagnosed until runtime. Add a `logger.warning`. |
| R13 | **Low** | `frontend/src/lib/useFlash.ts:17-18` | **`prev.current` updated before cleanup return.** If the component unmounts while a flash is active, `prev.current` has already been updated to the new value before the cleanup closure captures `id`. On re-mount, the stale `prev.current` may produce a spurious flash. Move the `prev.current` update after the timeout setup. |
| R14 | **Low** | `frontend/src/components/Watchlist.tsx:94` | **Placeholder-data flash.** After `api.addTicker` succeeds, the code sets `{ ticker, price: 0, change_pct: 0, ... }` as a placeholder until the next 5s REST refresh. The user sees a brief `$0.00 / 0.00%` blip. Set the current SSE price if available from the store, or skip the optimistic update. |
| R15 | **Low** | `backend/app/db/repository.py:31-32` | **`get_cash_balance` crashes on missing user.** `row["cash_balance"]` raises `TypeError` (subscript on `None`) when `user_id` does not exist. Return `0.0` or raise a domain error. |

### Regression risk note

The E2E test change in `test/e2e/chat.spec.ts` now uses `last()` matchers instead of `toHaveCount(1)`. If the page is reloaded mid-test for any reason (e.g., navigation retry logic), the chat history may be rehydrated with >1 bubbles from a previous run, and `last()` still matches — so the assertion is tolerant. This is correct, but the trade-off is that a truly empty chat panel would not be caught by these assertions (the test would silently pass even if no new bubble appeared). Consider asserting that at least one new bubble appeared (by comparing count before and after the send).

### Summary

The remediation is sound and the architectural choices (lock, async, extracted services) are proportionate. The new issues are concentrated in the newly written frontend library code (`useLiveData`, `api`, `store`, `Watchlist`) — the SSE error handling gap (R1) is the most actionable. The LLM feedback-loop gap (R3) is the most impactful for correctness but exists from the original build, not introduced by the remediation.
