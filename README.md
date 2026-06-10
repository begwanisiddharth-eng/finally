# FinAlly — AI Trading Workstation

A Bloomberg-style trading terminal with live market data, a simulated portfolio, and an AI assistant that can analyze positions and execute trades via natural language.

Built as a capstone project for an agentic AI coding course — the entire application is written by orchestrated AI coding agents.

## What it does

- **Live prices** — 10 default tickers streaming via SSE, flashing green/red on price change
- **Sparkline charts** — per-ticker mini-charts in the watchlist, plus a detailed chart for the selected ticker
- **Portfolio** — buy/sell shares at market price, track unrealized P&L via a heatmap and value chart
- **AI chat** — ask the assistant to analyze your portfolio, suggest trades, or execute them directly
- **Watchlist management** — add/remove tickers manually or via the AI

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (TypeScript), static export, Tailwind CSS, Zustand, Lightweight Charts |
| Backend | FastAPI (Python), served on port 8000 |
| Database | SQLite (`db/finally.db`), lazy-initialized on first run |
| Real-time | Server-Sent Events (SSE) |
| AI | LiteLLM → Groq (`groq/openai/gpt-oss-120b`) |
| Market data | GBM simulator (default) or Massive/Polygon.io API |

## Quick start

```bash
# macOS / Linux
cp .env.example .env          # add your GROQ_API_KEY
bash scripts/start_mac.sh

# Windows (PowerShell)
Copy-Item .env.example .env   # add your GROQ_API_KEY
.\scripts\start_windows.ps1
```

Open `http://localhost:8000`. No login required.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for the AI assistant |
| `MASSIVE_API_KEY` | No | Polygon.io key for real market data (simulator used if unset) |
| `LLM_MOCK` | No | Set to `true` for deterministic mock responses (E2E testing) |

## Development

```bash
cd backend
uv sync --extra dev       # install dependencies + dev tools
uv run pytest -v          # run tests
uv run ruff check app/    # lint
uv run market_data_demo.py  # live terminal price dashboard
```

## Testing

```bash
# Unit tests (backend)
cd backend && uv run pytest

# E2E tests (Playwright) — builds app, starts backend with LLM_MOCK=true
.\test\run_e2e.ps1        # Windows
bash test/run_e2e.sh      # macOS / Linux
```
