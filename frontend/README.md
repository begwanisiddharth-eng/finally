# FinAlly Frontend

Next.js (App Router, TypeScript) static export for the FinAlly trading workstation.
Served by the FastAPI backend from `frontend/out` at `http://localhost:8000`.

## Stack

- Next.js 16 with `output: 'export'` (static, single-origin, no CORS)
- Tailwind CSS, custom dark terminal theme
- Zustand for shared state (SSE prices, portfolio, watchlist, chat)
- TradingView Lightweight Charts for the price and P&L charts
- `EventSource` for the SSE price stream

## Commands

```bash
npm install
npm run build   # produces frontend/out
npm test        # Jest + React Testing Library
npm run dev     # local dev server (expects backend on /api)
```

All data comes from same-origin `/api/*` and `/api/stream/prices`.
