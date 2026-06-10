# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs a single start script. A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default tickers with live-updating prices in a grid
- $10,000 in virtual cash
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist

### What the User Can Do

- **Watch prices stream** — prices flash green (uptick) or red (downtick) with subtle CSS animations that fade
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation dialog
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat
- **Reset the portfolio** — restore $10,000 cash and clear all positions and trade history for a fresh start

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot (green = connected, yellow = reconnecting, red = disconnected) visible in the header
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)

## 3. Architecture Overview

### Single Process, Single Port

```
┌─────────────────────────────────────────────────┐
│  Local Process (port 8000)                      │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (local file)                   │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `db/finally.db`, persisted as a plain local file
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI integration**: LiteLLM → Groq (`groq/openai/gpt-oss-120b`) for fast inference, with structured outputs for trade execution
- **Market data**: Environment-variable driven — simulator by default, real data via Massive API if key provided

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one process, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| No container runtime | Students run one script; no Docker install required, nothing to orchestrate |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── db/                   # SQL schema files and seed logic (source-controlled)
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   └── ...                   # Additional agent reference docs
├── scripts/
│   ├── start_mac.sh          # Build frontend, launch backend (macOS/Linux)
│   ├── stop_mac.sh           # Stop the running backend (macOS/Linux)
│   ├── start_windows.ps1     # Build frontend, launch backend (Windows PowerShell)
│   └── stop_windows.ps1      # Stop the running backend (Windows PowerShell)
├── test/                     # Playwright E2E tests
│   ├── run_e2e.sh            # E2E test runner (macOS/Linux)
│   └── run_e2e.ps1           # E2E test runner (Windows)
├── db/                       # SQLite database file lives here at runtime (gitignored)
│   └── .gitkeep
├── .env                      # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/db/`** contains SQL schema files and seed logic checked into source control. The backend uses these to lazily initialize the database on first run.
- **`db/`** at the top level is where the SQLite file (`finally.db`) lives at runtime. It is created by the backend on first run, persists across restarts, and is gitignored. The `.gitignore` must contain `db/*.db` (not `db.sqlite3`) to cover `db/finally.db`.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and the `run_e2e.sh` / `run_e2e.ps1` scripts that build the app, launch it, and run the full suite.
- **`scripts/`** contains start/stop scripts that build the frontend and launch/stop the backend process.

---

## 5. Environment Variables

```bash
# Required: Groq API key for LLM chat functionality
GROQ_API_KEY=your-groq-api-key-here

# Optional: Massive (Polygon.io) API key for real market data
# If not set, the built-in market simulator is used (recommended for most users)
MASSIVE_API_KEY=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
# Read as a string — check with: os.getenv("LLM_MOCK", "false").lower() == "true"
LLM_MOCK=false
```

The backend reads `.env` from the project root on startup.

---

## 6. Market Data

### Two Implementations, One Interface

Both the simulator and the Massive client implement the same abstract interface. The backend selects which to use based on `MASSIVE_API_KEY`. All downstream code (SSE streaming, price cache, frontend) is agnostic to the source.

### Simulator (Default)

- Generates prices using geometric Brownian motion (GBM) with configurable drift and volatility per ticker
- Updates at ~500ms intervals
- Correlated moves across tickers (e.g., tech stocks move together)
- Occasional random "events" — sudden 2-5% moves on a ticker for drama
- Starts from realistic seed prices (e.g., AAPL ~$190, GOOGL ~$175, etc.)
- Runs as an in-process background task — no external dependencies

### Massive API (Optional)

- REST API polling (not WebSocket) — simpler, works on all tiers
- Polls for all tickers in the system on a configurable interval
- Free tier (5 calls/min): poll every 15 seconds
- Paid tiers: poll every 2-15 seconds depending on tier
- Parses REST response into the same format as the simulator

### Shared Price Cache

- A single background task (simulator or Massive poller) writes to an in-memory price cache
- The cache holds per ticker: latest price, previous price, session-open price (price at first observation this session), and timestamp
- **Session** = backend process lifetime; the session-open price resets each time the backend restarts. It is not tied to calendar day or midnight.
- `session_open` is stored in a separate dict within `PriceCache`, set the **first time** a ticker is updated per process lifetime and **never overwritten** thereafter. It must be exposed via a `get_session_open(ticker)` method and included in every SSE event and `GET /api/watchlist` response.
- The session-open price enables the frontend to display change since session start
- SSE streams read from this cache and push updates to connected clients

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- Server pushes price updates for **all tickers in the system** at a regular cadence (~500ms)
- Each SSE `data:` line is a **single-ticker JSON object** — do not batch multiple tickers into one event. One event per ticker per cadence tick.
- Fields: `ticker`, `price`, `prev_price`, `session_open`, `change_pct`, `direction`, `timestamp`. The names `prev_price` and `change_pct` are the exact wire contract and must match the `GET /api/watchlist` response exactly.
- The `timestamp` field is an ISO 8601 string (e.g., `"2026-01-01T10:00:00Z"`), not a Unix timestamp float.
- Client handles reconnection automatically (EventSource has built-in retry)
- **Scalability note**: pushing all tickers every ~500ms is fine for the default 10–20 ticker watchlist. At 50+ tickers, delta-only updates or per-ticker SSE topics should be considered (future optimization, not in scope).

---

## 7. Database

### SQLite with Lazy Initialization

The backend checks for the SQLite database on startup. If the file doesn't exist or tables are missing, it creates the schema and seeds default data — no separate migration step, no manual setup.

Enable WAL mode (`PRAGMA journal_mode=WAL`) on connection open. This allows the background snapshot writer and trade-execution writes to coexist without blocking each other, since WAL permits concurrent readers and one writer.

**Single-user design**: every table has a `user_id` column defaulting to `"default"`. This is a forward-compatibility stub — it is never varied in this app. Multi-user support would be trivial to add later but is explicitly out of scope.

### Schema

**users_profile** — User state (cash balance)
- `user_id` TEXT PRIMARY KEY (default: `"default"`)
- `cash_balance` REAL (default: `10000.0`)
- `created_at` TEXT (ISO timestamp)

**watchlist** — Tickers the user is watching
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**positions** — Current holdings (one row per ticker per user)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `quantity` REAL (fractional shares supported; minimum increment 0.001)
- `avg_cost` REAL
- `updated_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**trades** — Trade history (append-only log)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` or `"sell"`)
- `quantity` REAL (fractional shares supported; minimum increment 0.001)
- `price` REAL
- `executed_at` TEXT (ISO timestamp)

**portfolio_snapshots** — Portfolio value over time (for P&L chart). Recorded every 30 seconds by a background task, and immediately after each trade execution.
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `total_value` REAL
- `recorded_at` TEXT (ISO timestamp)

**chat_messages** — Conversation history with LLM
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — serialized object containing `trades`, `watchlist_changes`, `trade_results`, `watchlist_results` as returned by `POST /api/chat`; null for user messages and assistant messages with no actions)
- `created_at` TEXT (ISO timestamp)

### Default Seed Data

- One user profile: `user_id="default"`, `cash_balance=10000.0`
- Ten watchlist entries: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

---

## 8. API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, quantity, side}` |
| GET | `/api/portfolio/history` | Portfolio value snapshots over time (for P&L chart) |
| POST | `/api/portfolio/reset` | Reset to $10,000 cash, clear all positions and trade history |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Current watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |

`GET /api/watchlist` provides the initial snapshot on page load; live price updates after that arrive via `/api/stream/prices`.

`POST /api/watchlist` validates that the ticker is a non-empty string of 1–10 uppercase alphanumeric characters. It does **not** verify the ticker exists in any external registry — the simulator accepts any valid ticker and will begin generating prices for it immediately.

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send `{message}`, receive structured response with executed actions |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |

### Standard Error Envelope

All non-2xx responses use this shape:
```json
{"ok": false, "error": "Human-readable message"}
```
`POST /api/portfolio/trade` uses `400`. Other endpoints use `400` for bad input, `404` for not found, `500` for unexpected errors.

### Response Shapes

**`GET /api/portfolio`**
```json
{
  "cash_balance": 8500.00,
  "total_value": 11234.56,
  "positions": [
    {
      "ticker": "AAPL",
      "quantity": 10,
      "avg_cost": 190.00,
      "current_price": 195.50,
      "market_value": 1955.00,
      "unrealized_pnl": 55.00,
      "pnl_pct": 2.89
    }
  ]
}
```

**`GET /api/watchlist`**
```json
[
  {
    "ticker": "AAPL",
    "price": 195.50,
    "prev_price": 194.20,
    "session_open": 190.00,
    "change_pct": 2.89
  }
]
```

**`GET /api/portfolio/history`**
```json
[
  {"recorded_at": "2026-01-01T10:00:00Z", "total_value": 10000.00},
  {"recorded_at": "2026-01-01T10:00:30Z", "total_value": 10045.50}
]
```

**`POST /api/portfolio/trade`** — request: `{ticker, quantity, side}`

Success `200`:
```json
{
  "ok": true,
  "ticker": "AAPL",
  "side": "buy",
  "quantity": 10,
  "price": 195.50,
  "executed_at": "2026-01-01T10:00:00Z",
  "cash_balance": 8544.00
}
```
Error `400`:
```json
{"ok": false, "error": "Insufficient cash"}
```

**`POST /api/portfolio/reset`**
```json
{"ok": true}
```

**`POST /api/chat`** — request: `{message}`
```json
{
  "message": "I've bought 10 shares of AAPL for you.",
  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
  "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
  "trade_results": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10, "price": 195.50, "ok": true}
  ],
  "watchlist_results": [
    {"ticker": "PYPL", "action": "add", "ok": true}
  ]
}
```

**`GET /api/health`**
```json
{"status": "ok"}
```
Returns `200` if the process is running and the DB is reachable (simple `SELECT 1` check).

**SSE event** (`GET /api/stream/prices`)
```json
{
  "ticker": "AAPL",
  "price": 195.50,
  "prev_price": 194.20,
  "session_open": 190.00,
  "change_pct": 2.89,
  "direction": "up",
  "timestamp": "2026-01-01T10:00:00Z"
}
```

---

## 9. LLM Integration

See `backend/CLAUDE.md` for the implementation instruction (which skill and model to use).

### How It Works

When the user sends a chat message, the backend:

1. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value)
2. Loads the most recent 20 messages of conversation history from the `chat_messages` table
3. Constructs a prompt with a system message, portfolio context, conversation history, and the user's new message
4. Calls the LLM via LiteLLM → Groq, requesting structured output
5. Parses the complete structured JSON response
6. Auto-executes any trades or watchlist changes specified in the response
7. Stores the message and executed actions in `chat_messages`
8. Returns the complete JSON response to the frontend (no token-by-token streaming — Groq inference is fast enough that a loading indicator is sufficient)

### Structured Output Schema

The LLM responds with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `trades` (optional): Array of trades to auto-execute, routed through the same shared trade-validation/execution function used by `POST /api/portfolio/trade` — one code path, no duplicated checks
- `watchlist_changes` (optional): Array of watchlist modifications; `action` is `"add"` or `"remove"`

### Auto-Execution

Trades specified by the LLM execute automatically — no confirmation dialog. It's a simulated environment, so the stakes are zero; this creates an impressive, fluid demo and demonstrates agentic AI capabilities.

If a trade fails validation (e.g., insufficient cash), the error is included in the chat response so the LLM can inform the user.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when the user asks or agrees
- Manage the watchlist proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### Rate Limiting

The frontend disables the chat submit button while a request is in flight (one request at a time). This is sufficient to prevent accidental Groq quota exhaustion in normal use — no server-side rate limiter needed for this single-user demo.

### LLM Mock Mode

When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling Groq, enabling fast, reproducible E2E tests and development without an API key.

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watched tickers with: ticker symbol, current price (flashing green/red on change), session change %, and a sparkline mini-chart (accumulated from SSE since page load)
- **Main chart area** — larger chart for the currently selected ticker showing price over time, built from SSE data accumulated since page load (chart starts empty and fills progressively). Clicking a ticker in the watchlist selects it.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss)
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots`
- **Positions table** — tabular view of all positions: ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Trade bar** — simple input area: ticker field, quantity field, buy button, sell button. Includes a reset button to restore the starting balance.
- **AI chat panel** — docked/collapsible sidebar. Message input, scrolling conversation history, loading indicator while waiting for LLM response. Trade executions and watchlist changes shown inline as confirmations.
- **Header** — portfolio total value (updating live), connection status indicator, cash balance

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`
- **Charting library: Lightweight Charts** (TradingView) — canvas-based, purpose-built for financial time series, matches the terminal aesthetic. Do not use Recharts (SVG-based, not suited for high-frequency updates).
- Price flash effect: on receiving a new price, briefly apply a CSS class with background color transition, then remove it
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme
- **State management: Zustand** — lightweight, no boilerplate, easy to share SSE price state, positions, and chat history across components without prop drilling
- **Known limitation**: sparkline data is accumulated in memory from SSE since page load and is lost on refresh. This is intentional for simplicity; a `price_history` table would be needed for persistence.

---

## 11. Running & Deployment

The start scripts build the frontend static export and launch the FastAPI backend directly via `uv` on port 8000. See §3 for the architecture diagram.

### Start/Stop Scripts

**`scripts/start_mac.sh`** (macOS/Linux):
- Builds the frontend static export (`npm install && npm run build`)
- Installs backend dependencies (`uv sync`)
- Launches the backend and prints the URL; opens the browser by default (pass `--no-browser` to skip)

**`scripts/stop_mac.sh`** (macOS/Linux):
- Stops the running backend process
- Leaves `db/finally.db` untouched (data persists)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: PowerShell equivalents.

All scripts are idempotent — safe to run multiple times.

### Backend Dependencies

The backend `pyproject.toml` must explicitly declare these as direct dependencies (not just rely on transitive installs):
- `python-dotenv` — loads `.env` at startup
- `litellm` — LLM integration (§9)
- `aiosqlite` — async SQLite driver required for async FastAPI route handlers

`rich` is only used by the dev demo script and belongs in `optional-dependencies.dev`, not `dependencies`.

### Database

The SQLite database persists at `db/finally.db`. The backend creates and seeds it on first run — no separate setup step required.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid prices, GBM math is correct, Massive API response parsing works, both implementations conform to the abstract interface
- Portfolio: trade execution logic, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Entry points**: `test/run_e2e.sh` (macOS/Linux) and `test/run_e2e.ps1` (Windows). Each script builds the frontend, launches the backend with `LLM_MOCK=true`, and runs Playwright against `http://localhost:8000`.

**Key Scenarios**:
- Fresh start: default watchlist appears, $10k balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio reset: cash restores to $10k, positions cleared
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection

---

## 13. Market Data Component: Status and Pre-Build Checklist for Next Phase

The market data subsystem (`backend/app/market/`) is complete and spec-compliant. All blocking and recommended fixes from the initial review were applied in commit `1fbdd7b`. 79 tests pass, ruff linting is clean.

### Resolved (commit `1fbdd7b`)

`session_open` in `PriceCache`, SSE per-ticker events, `prev_price`/`change_pct` wire names, ISO 8601 timestamps, `timestamp=0.0` falsy fix, GBM `dt` decoupled from `update_interval`, module-level router bug, `MassiveDataSource` ticker normalization, dead `conftest.py` fixture removed, `rich` moved to dev dependencies.

### Blocking fixes before building portfolio/watchlist/chat

- **Missing backend dependencies**: Add `python-dotenv`, `litellm`, and `aiosqlite` to `dependencies` in `pyproject.toml`. These are required by §5 (env loading), §9 (LLM), and §7 (async database) respectively. Do not rely on transitive installs.
- **`.env.example` missing**: Create at the project root with placeholder values for `GROQ_API_KEY`, `MASSIVE_API_KEY`, and `LLM_MOCK` (as documented in §5).
- **`db/finally.db` not gitignored**: The `.gitignore` currently uses `db.sqlite3` (Django convention). Change to `db/*.db` to cover the actual runtime path `db/finally.db` (per §4).

### Recommended fixes (minor, clean up before proceeding)

- **SSE generator silent error swallowing** (`stream.py`): The `while True` loop catches only `asyncio.CancelledError`. An unexpected `Exception` (e.g., from `price_cache.get_all()` or `json.dumps()`) would close the SSE stream without logging. Add a broad `except Exception` with a `logger.exception()` call around the loop body.
- **Fragile rounding assertion** (`tests/market/test_simulator.py`): `assert len(decimal_part) <= 2` allows 0 or 1 decimal places. Replace with `assert round(result["AAPL"], 2) == result["AAPL"]`.
- **Test accesses private attribute** (`tests/market/test_simulator.py`): `assert len(sim._tickers) == 1` should use `assert len(sim.get_tickers()) == 1`.
