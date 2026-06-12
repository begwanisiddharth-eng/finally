# FinAlly — AI Trading Workstation

## 1. Vision

FinAlly (Finance Ally) is an AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

## 2. User Experience

### First Launch

The user runs a single start script. A browser opens to `http://localhost:8000`. No login, no signup. They immediately see a watchlist of 10 default tickers with live-updating prices, $10,000 in virtual cash, and an AI chat panel ready to assist.

### What the User Can Do

- **Watch prices stream** — prices flash green/red with CSS animations that fade over ~500ms
- **View sparkline mini-charts** — accumulated from the SSE stream since page load
- **Click a ticker** to see a larger chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation
- **Monitor their portfolio** — treemap heatmap (positions sized by weight, colored by P&L) + P&L chart
- **View a positions table** — ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about the portfolio, get analysis, have the AI execute trades and manage the watchlist
- **Manage the watchlist** — add/remove tickers manually or via AI chat
- **Reset the portfolio** — restore $10,000 cash and clear all positions and trade history

### Visual Design

- **Dark theme**: backgrounds `#0d1117` / `#1a1a2e`, muted gray borders
- **Price flash**: brief green/red background highlight on price change, fades via CSS transition
- **Connection status**: colored dot in header (green = connected, yellow = reconnecting, red = disconnected)
- **Desktop-first**: optimized for wide screens, functional on tablet
- **Color scheme**: Accent Yellow `#ecad0a` · Blue Primary `#209dd7` · Purple Secondary `#753991` (submit buttons)

---

## 3. Architecture

```
┌─────────────────────────────────────────────────┐
│  Local Process (port 8000)                      │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static files (Next.js)     │
│  SQLite (db/finally.db)                         │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

| Stack choice | Rationale |
|---|---|
| SSE over WebSockets | One-way push is sufficient; simpler, universal browser support |
| Static Next.js export | Single origin, no CORS, one port, one process |
| SQLite over Postgres | Single-user, self-contained, zero config |
| No container runtime | Students run one script; no Docker required |
| uv for Python | Fast, modern, reproducible lockfile |
| Market orders only | Eliminates order book / partial-fill complexity |

- **Frontend**: Next.js + TypeScript, static export (`output: 'export'`), served by FastAPI
- **Backend**: FastAPI, `uv` project
- **AI**: LiteLLM → Groq (`groq/openai/gpt-oss-120b`), structured outputs
- **Market data**: simulator by default; Massive (Polygon.io) REST API if `MASSIVE_API_KEY` is set

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project
│   └── db/                   # SQL schema + seed logic (source-controlled)
├── planning/                 # Agent reference docs
├── scripts/
│   ├── start_mac.sh / stop_mac.sh
│   └── start_windows.ps1 / stop_windows.ps1
├── test/
│   ├── run_e2e.sh / run_e2e.ps1
├── db/                       # SQLite file at runtime (gitignored)
│   └── .gitkeep
├── .env                      # Gitignored; .env.example committed
└── .gitignore
```

- `frontend/` talks to the backend only via `/api/*` and `/api/stream/*`
- `backend/` owns all server logic: DB init, API routes, SSE, market data, LLM
- `db/finally.db` is created on first run, persists across restarts
- `test/` scripts build the app, launch it with `LLM_MOCK=true`, and run the Playwright suite

---

## 5. Environment Variables

```bash
GROQ_API_KEY=your-groq-api-key-here   # Required: LLM chat
MASSIVE_API_KEY=                        # Optional: real market data (simulator used if unset)
LLM_MOCK=false                          # Set "true" for deterministic mock responses in tests
```

The backend reads `.env` from the project root on startup.

---

## 6. Market Data

### Two Implementations, One Interface

Both implement the same `MarketDataSource` ABC. The backend selects based on `MASSIVE_API_KEY`. All downstream code is agnostic to the source.

**Simulator (default)** — GBM prices with configurable drift/volatility, correlated moves, random 2–5% shock events, 500ms update interval, in-process background task.

**Massive API (optional)** — REST polling; 15s interval on free tier (5 req/min), 2–15s on paid tiers.

### Price Cache

One background task writes to an in-memory `PriceCache`; all consumers read from it.

- Per ticker: latest price, previous price, `session_open` (first price this process lifetime), timestamp
- `session_open` is set once on first update and never overwritten; resets on backend restart
- `version` counter bumped on every update — SSE generator uses it for change detection

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- One `data:` event per ticker per ~500ms cadence — never batched
- Wire fields: `ticker`, `price`, `prev_price`, `session_open`, `change_pct`, `direction`, `timestamp`
- `prev_price` and `change_pct` are the exact field names (match `GET /api/watchlist`)
- `timestamp` is ISO 8601 string, not a Unix float
- `retry: 1000` — browser reconnects after 1s if dropped

---

## 7. Database

SQLite, lazy-initialized on first run (schema + seed data created automatically). Enable WAL mode on connection open.

Every table has `user_id TEXT DEFAULT "default"` — a forward-compatibility stub, never varied.

### Schema

**users_profile** — `user_id` PK, `cash_balance` REAL (10000.0), `created_at`

**watchlist** — `id` UUID PK, `user_id`, `ticker`, `added_at`; UNIQUE `(user_id, ticker)`

**positions** — `id` UUID PK, `user_id`, `ticker`, `quantity` REAL, `avg_cost` REAL, `updated_at`; UNIQUE `(user_id, ticker)`. Fractional shares supported (min 0.001).

**trades** — `id` UUID PK, `user_id`, `ticker`, `side` ("buy"/"sell"), `quantity` REAL, `price` REAL, `executed_at`. Append-only.

**portfolio_snapshots** — `id` UUID PK, `user_id`, `total_value` REAL, `recorded_at`. Written every 30s by background task and immediately after each trade.

**chat_messages** — `id` UUID PK, `user_id`, `role` ("user"/"assistant"), `content`, `actions` (JSON or null), `created_at`

### Seed Data

- `users_profile`: `user_id="default"`, `cash_balance=10000.0`
- `watchlist`: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

---

## 8. API Endpoints

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE live price stream |
| GET | `/api/portfolio` | Positions, cash, total value, P&L |
| POST | `/api/portfolio/trade` | Execute trade: `{ticker, quantity, side}` |
| GET | `/api/portfolio/history` | Portfolio value snapshots (P&L chart) |
| POST | `/api/portfolio/reset` | Reset to $10k, clear positions + trades |
| GET | `/api/watchlist` | Watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Remove ticker |
| POST | `/api/chat` | Send `{message}`, get structured response |
| GET | `/api/chat/history` | Recent chat messages (UI rehydration on load) |
| GET | `/api/health` | Health check (`SELECT 1` on DB) |

`POST /api/watchlist` validates 1–10 uppercase alphanumeric characters; does not verify the ticker exists externally.

### Error Envelope

```json
{"ok": false, "error": "Human-readable message"}
```

`400` for bad input / failed trades, `404` for not found, `500` for unexpected errors.

### Response Shapes

**`GET /api/portfolio`**
```json
{
  "cash_balance": 8500.00,
  "total_value": 11234.56,
  "positions": [
    {"ticker": "AAPL", "quantity": 10, "avg_cost": 190.00,
     "current_price": 195.50, "market_value": 1955.00,
     "unrealized_pnl": 55.00, "pnl_pct": 2.89}
  ]
}
```

**`GET /api/watchlist`**
```json
[{"ticker": "AAPL", "price": 195.50, "prev_price": 194.20, "session_open": 190.00, "change_pct": 2.89}]
```

**`GET /api/portfolio/history`**
```json
[{"recorded_at": "2026-01-01T10:00:00Z", "total_value": 10000.00}]
```

**`POST /api/portfolio/trade`** — success `200` / error `400`
```json
{"ok": true, "ticker": "AAPL", "side": "buy", "quantity": 10,
 "price": 195.50, "executed_at": "2026-01-01T10:00:00Z", "cash_balance": 8544.00}
```

**`POST /api/portfolio/reset`** — `{"ok": true}`. Clears positions, trades, snapshots; restores cash to 10000.0. Chat history preserved.

**`POST /api/chat`**
```json
{
  "message": "I've bought 10 shares of AAPL for you.",
  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
  "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
  "trade_results": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10, "price": 195.50, "ok": true},
    {"ticker": "ZZZZ", "side": "buy", "quantity": 5, "ok": false, "error": "Insufficient cash"}
  ],
  "watchlist_results": [
    {"ticker": "PYPL", "action": "add", "ok": true}
  ]
}
```

**SSE event**
```json
{"ticker": "AAPL", "price": 195.50, "prev_price": 194.20, "session_open": 190.00,
 "change_pct": 2.89, "direction": "up", "timestamp": "2026-01-01T10:00:00Z"}
```

---

## 9. LLM Integration

See `backend/CLAUDE.md` for model and skill details.

### Flow

1. Load portfolio context (cash, positions with P&L, watchlist with live prices)
2. Load last 20 messages from `chat_messages`
3. Construct prompt: system message + portfolio context + history + user message
4. Call LLM via LiteLLM → Groq, request structured output
5. Auto-execute any trades and watchlist changes (same validation path as `POST /api/portfolio/trade`)
6. Store message + actions in `chat_messages`
7. Return full JSON response (no streaming — loading indicator is sufficient)

### Structured Output Schema

```json
{
  "message": "Conversational response shown to user",
  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10.0}],
  "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]
}
```

`trades` and `watchlist_changes` are optional. `quantity` is a positive float, min 0.001.

### System Prompt Guidance

Prompt the LLM as "FinAlly, an AI trading assistant." It should: analyze portfolio composition, risk, and P&L; suggest and execute trades when asked; manage the watchlist proactively; be concise and data-driven; always respond with valid structured JSON.

### Mock Mode

`LLM_MOCK=true` returns deterministic mock responses — no API key needed, used for E2E tests.

---

## 10. Frontend

### Layout Elements

- **Watchlist panel** — ticker, price (flashing on change), session change %, sparkline (SSE-accumulated)
- **Main chart area** — selected ticker price history, fills progressively from SSE data
- **Portfolio heatmap** — treemap: positions sized by weight, colored by P&L
- **P&L chart** — total portfolio value over time from `portfolio_snapshots`
- **Positions table** — ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Trade bar** — ticker + quantity inputs, buy/sell buttons, reset button
- **AI chat panel** — docked sidebar: message input, scrolling history, loading indicator, inline trade confirmations
- **Header** — live total value, connection status dot, cash balance

### Technical Choices

- `EventSource` for SSE (`/api/stream/prices`)
- **Charting: Lightweight Charts** (TradingView) — canvas-based, built for financial time series. Not Recharts.
- Price flash: CSS class applied on price change, removed after transition
- **Tailwind CSS** with custom dark theme
- **Zustand** for state management — SSE prices, positions, chat history shared across components
- All API calls to same origin (`/api/*`) — no CORS needed
- Sparkline data is in-memory only; lost on refresh (intentional)

---

## 11. Scripts & Database

**Start scripts** (`scripts/start_mac.sh` / `scripts/start_windows.ps1`):
1. `npm install && npm run build` in `frontend/`
2. `uv sync` in `backend/`
3. Launch FastAPI on port 8000; open browser (pass `--no-browser` to skip)

**Stop scripts** leave `db/finally.db` untouched.

`db/finally.db` is created and seeded on first run. No separate migration step.

---

## 12. Testing

### Backend (pytest in `backend/`)

- Market data: GBM math, simulator prices, Massive response parsing, both sources conform to ABC
- Portfolio: trade execution, P&L calculations, edge cases (insufficient cash, oversell, loss)
- LLM: structured output parsing, malformed response handling, trade validation in chat flow
- API routes: status codes, response shapes, error handling

### Frontend (React Testing Library)

- Component rendering with mock data
- Price flash triggers on price change
- Watchlist CRUD, portfolio calculations, chat rendering

### E2E (Playwright in `test/`)

Runner: `test/run_e2e.sh` / `test/run_e2e.ps1` — builds app, starts backend with `LLM_MOCK=true`, runs against `http://localhost:8000`.

Scenarios: fresh start, add/remove ticker, buy/sell shares, portfolio reset, heatmap + P&L chart, AI chat (mocked), SSE reconnection.

---

## 13. Build Status

### Market Data — Complete

`backend/app/market/` — 79 tests pass, 0 fail. Ruff clean.

| Module | Tests |
|---|---|
| `models.py` | 11 |
| `cache.py` | 18 |
| `simulator.py` — GBMSimulator | 17 |
| `simulator.py` — SimulatorDataSource | 9 |
| `massive_client.py` | 13 |
| `factory.py` | 7 |
| `stream.py` | 0 — no unit tests (covered by E2E) |
| `interface.py`, `seed_prices.py`, `__init__.py` | covered above |

Planning docs: `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, `MASSIVE_API.md` — all in sync with the implementation.

### Backend — Complete (review-hardened)

Built by an agent team (db / api / llm engineers), then hardened against the code review (see `REVIEW.md`). `backend/` — **152 tests pass, 0 fail. Ruff clean.** (79 market + 28 db + 16 api + 29 llm.)

**Database layer** — `app/db/` (`schema.sql`, `connection.py`, `repository.py`, `__init__.py`).
- 6 tables per §7; TEXT UUID PKs; `user_id TEXT DEFAULT 'default'` everywhere; UNIQUE `(user_id,ticker)` on watchlist + positions.
- All timestamps are **ISO-8601 UTC** (`strftime('%Y-%m-%dT%H:%M:%SZ','now')`) so `executed_at`/`recorded_at` match the spec and parse unambiguously in the browser.
- `connect(path=None)`: aiosqlite, `PRAGMA journal_mode=WAL`, `row_factory=Row`, lazy schema (CREATE IF NOT EXISTS) + idempotent seed ($10k default user, 10 default tickers). Path = `project_root/db/finally.db`, overridable via `FINALLY_DB_PATH` (used by E2E for a throwaway DB).
- Async repo primitives: cash get/set, watchlist list/add/remove, positions get/list/upsert/delete, trades insert/list, snapshots insert/list, chat insert/list-recent-N, `reset_portfolio` (preserves watchlist + chat). 28 tests.

**Portfolio & watchlist API + trade engine** — `app/api/` + `app/services/` + `app/main.py`.
- `services/trades.execute_trade(conn, cache, ticker, side, quantity)` — shared engine: cash/holdings validation, avg-cost recompute on buy, position removal on full sell, inserts trade + writes snapshot; raises `TradeError`. The order is serialized under `services/locks.db_write_lock` so concurrent trades / the snapshot task cannot interleave or lose updates. Reset and the snapshot loop take the same lock.
- `services/portfolio.build_portfolio()` / `compute_total_value()`; `services/watchlist.execute_watchlist_change()` (mutations) and `build_watchlist_view()` (price-shaped read) — single shared paths used by REST routes **and** chat.
- Routes: `GET /api/portfolio`, `POST /api/portfolio/trade`, `GET /api/portfolio/history`, `POST /api/portfolio/reset`, `GET/POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`, `GET /api/health`. Error envelope `{"ok": false, "error": ...}` with 400/404/500 handlers (validation errors summarized to field names, no internals leaked).
- `main.create_app()` + lifespan: connect DB, one shared `PriceCache`, `create_market_data_source`, `source.start(watchlist)`, mount SSE router, 30s snapshot background task. Serves `frontend/out` at `/*`. Module-level `app` → entrypoint `uvicorn app.main:app`. 16 tests.

**Chat / LLM integration** — `app/llm/` + `app/api/chat.py`.
- `schema.py` (ChatResponse/TradeAction/WatchlistAction, quantity min 0.001), `prompt.py` (system prompt + portfolio context + history assembly), `client.py` (**async** LiteLLM `acompletion` → Groq `groq/openai/gpt-oss-120b`, structured outputs, tenacity backoff — does not block the event loop / SSE stream), `mock.py` (deterministic `LLM_MOCK=true`, no network), `service.py` (load context via shared services + last 20 messages → LLM/mock → auto-execute via shared services → persist → return §8 shape).
- `POST /api/chat` self-wires via `main._include_chat_router()`; `GET /api/chat/history` returns recent messages for UI rehydration. 29 tests.

### Frontend — Built

`frontend/` — Next.js + TypeScript static export (`output: 'export'` → `frontend/out` built). Tailwind dark theme, Zustand store, TradingView Lightweight Charts, `EventSource` SSE with price-flash + connection-status dot.
- Components: `Header`, `Watchlist` (+ `Sparkline`), `MainChart`, `Heatmap`, `PnlChart`, `PositionsTable`, `TradeBar`, `ChatPanel`, `Dashboard`.
- `lib/`: `store.ts`, `api.ts`, `types.ts`, `useLiveData.ts`, `useFlash.ts`, `format.ts`. On load, `useLiveData` rehydrates chat history from `GET /api/chat/history` so the UI matches what the model remembers. Watchlist rows are valid (non-nested) interactive elements. Component + lib tests (React Testing Library / Jest) — **29 pass**.

### Scripts & E2E — Complete, full gate GREEN

- `scripts/` — `start_windows.ps1`, `stop_windows.ps1`, `start_mac.sh`, `stop_mac.sh` (build frontend, `uv sync`, launch `uvicorn app.main:app` bound to **`127.0.0.1`**, open the browser only after `/api/health` responds, `--no-browser`/`-NoBrowser` to skip; stop leaves `db/finally.db` untouched).
- `test/` — `run_e2e.ps1` / `run_e2e.sh` (build, start backend `LLM_MOCK=true` against a throwaway `FINALLY_DB_PATH` DB, wait on `/api/health`, run Playwright, tear down + delete the throwaway DB). Playwright project + `e2e/selectors.ts` + **25 tests** across all §12 scenarios.
- **Full E2E gate: GREEN — 25/25 pass (~15s)** via `test/run_e2e.ps1` against a real clean build (`uvicorn app.main:app` serving `frontend/out`, `LLM_MOCK=true`): fresh-start (10 tickers, $10k, SSE flash), watchlist add/remove (UI + API validation), buy/sell + insufficient-cash/oversell rejection, reset, heatmap + P&L + main chart render, chat-mock (exact messages, real trade execution, watchlist update, ok:false on over-cash), SSE reconnection.
- Note: runner/Playwright `baseURL` use `127.0.0.1` (not `localhost`) to match uvicorn's IPv4 bind — on Windows `localhost` prefers IPv6 `::1`, which the IPv4-only server doesn't answer, hanging the health probe.
