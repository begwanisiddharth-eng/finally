# FinAlly E2E Tests

Playwright end-to-end suite covering PLAN.md section 12 scenarios.

## Run

Windows:

```powershell
./run_e2e.ps1
```

macOS / Linux:

```bash
./run_e2e.sh
```

Each runner builds the frontend, syncs the backend, starts FastAPI with
`LLM_MOCK=true` on port 8000, waits for `/api/health`, then runs the suite
against `http://localhost:8000` and tears the backend down.

## Specs

| File | Scenario |
|---|---|
| `fresh-start.spec.ts` | 10 default tickers, $10k cash, prices stream |
| `watchlist.spec.ts` | Add / remove ticker, input validation |
| `trade.spec.ts` | Buy / sell shares, insufficient cash, oversell |
| `reset.spec.ts` | Portfolio reset restores $10k, clears positions |
| `charts.spec.ts` | Heatmap, P&L chart, main chart render |
| `chat.spec.ts` | AI chat with deterministic `LLM_MOCK` responses |
| `sse-reconnect.spec.ts` | SSE drop + auto-reconnect, prices resume |

## Selectors

All `data-testid` selectors are centralized in `e2e/selectors.ts`. Update that
one file if the frontend changes its testids.
