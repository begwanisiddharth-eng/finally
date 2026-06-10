# FinAlly — AI Trading Workstation

A dark-themed, Bloomberg-style trading terminal with live streaming prices, a simulated portfolio, and an AI chat assistant that can analyze positions and execute trades.

## Quick Start

```powershell
# Copy and fill in your Groq API key
cp .env.example .env

# Start the app (builds frontend, launches backend on port 8000)
.\scripts\start_windows.ps1
```

Then open [http://localhost:8000](http://localhost:8000).

To stop: `.\scripts\stop_windows.ps1`

## Features

- Live price streaming via SSE with green/red flash animations
- Simulated portfolio — buy/sell with market orders, track P&L
- Portfolio heatmap (treemap) and P&L history chart
- AI chat assistant (Groq) that can execute trades and manage the watchlist
- Watchlist management — add/remove tickers manually or via chat
- Portfolio reset to restore $10k starting balance

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for AI chat |
| `MASSIVE_API_KEY` | No | Polygon.io key for real market data (simulator used if unset) |
| `LLM_MOCK` | No | Set `true` for mock LLM responses (E2E tests) |

## Stack

- **Frontend**: Next.js (TypeScript, static export), Tailwind CSS, Zustand, Lightweight Charts
- **Backend**: FastAPI + Python (`uv`), SQLite, LiteLLM → Groq
- **Real-time**: Server-Sent Events (SSE)

## Running Tests

```powershell
# Backend unit tests
cd backend
uv run pytest -v

# E2E tests (Playwright)
.\test\run_e2e.ps1
```
