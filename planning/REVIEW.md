# Review of PLAN.md

## Overall

The plan is well-structured, opinionated, and clear. The architecture decisions (SSE over WebSockets, static Next.js export, SQLite, single-port deployment) are justified and consistent. Below are observations, questions, and suggestions.

## Strengths

- **Single-process, single-port** approach eliminates deployment complexity, CORS issues, and multi-service orchestration. Excellent choice for a demo/capstone.
- **SSE vs WebSockets** reasoning is sound — one-way push is sufficient, and built-in `EventSource` reconnection simplifies client code.
- **Lazy DB initialization** removes migration friction. Pairing schema files in `backend/db/` with runtime data in `db/` (gitignored) is clean.
- **Mock LLM mode** is essential for reproducible testing and development without API keys.
- **Structured LLM output** with auto-execution makes the demo impressive and avoids cumbersome confirmation dialogs in a simulated environment.

## Concerns & Suggestions

### 1. Missing Error Handling Specifications

The API response shapes don't cover error cases except `POST /api/portfolio/trade` (400). At minimum, the plan should specify a consistent error envelope:

```json
{"ok": false, "error": "message", "detail": {}}
```

Used across all endpoints — `POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`, `POST /api/chat`, and `GET /api/portfolio/history` (what if no data?).

### 2. SSE Payload Inefficiency

Pushing *all* tickers every ~500ms is wasteful at scale. For 10 tickers it's fine, but the spec should note that if the watchlist grows (say, 50+ tickers), delta-only updates or per-ticker SSE topics should be considered. A brief "future optimization" note would suffice.

### 3. Fractional Shares vs. Integer Shares

The schema uses `quantity REAL` and mentions "fractional shares supported," but the frontend trade bar shows a quantity field without specifying precision. What's the minimum increment (0.001? 0.01?)? The plan should define this to avoid frontend/backend mismatch.

### 4. Database Concurrency

SQLite is single-writer. The background snapshot task writes to `portfolio_snapshots` every 30s while trades also write. If a trade and snapshot collide, the write queue handles it, but a brief note acknowledging this and confirming WAL mode or retry logic would inspire confidence.

### 5. Watchlist Add Validation

`POST /api/watchlist` accepts `{ticker}`. Can any string be added? Should there be validation that the ticker exists in the market data system? A simulator that generates prices for *any* ticker sidesteps this, but the plan should note it — or explicitly state that the simulator accepts any ticker dynamically.

### 6. Frontend Charting Library

The plan mentions "Lightweight Charts or Recharts" as a note. These are fundamentally different: Lightweight Charts is canvas-based (TradingView), Recharts is SVG-based. The plan should pick one. Given the terminal aesthetic and performance requirements, Lightweight Charts is a better fit.

### 7. Missing: Rate Limiting / Abuse Prevention

`POST /api/chat` calls an external LLM API (Groq). Nothing prevents a user from spamming the chat endpoint and burning through API quota. A simple rate limiter (e.g., 1 request per second, or a client-side cooldown) should be mentioned.

### 8. Missing: Frontend State Management

The plan specifies UI elements but not how state is managed. SSE updates, trade responses, and chat responses all modify overlapping state (prices, positions, cash). A brief mention of the state management approach (React Context, Zustand, Redux) would reduce ambiguity for the Frontend Engineer.

### 9. Trailing Stop / Session Price Ambiguity

The SSE event includes `session_open` — price at first observation this session. "Session" is not clearly defined. Is a session the backend process lifetime? A calendar day? Midnight reset? This matters for the "change since session start" display.

### 10. Chat Actions Formatting

The `chat_messages.actions` column stores JSON, but the plan doesn't specify its schema clearly. The `POST /api/chat` response breaks actions into `trades`, `watchlist_changes`, `trade_results`, `watchlist_results`. Does the `actions` column store the combined object? The response object? Clarify.

### 11. No Health Check Criteria

`GET /api/health` exists but no success/response shape is defined. Should it return `{"status": "ok"}`? Should it verify DB connectivity? Market data heartbeat? A lightweight health check spec would help.

### 12. Missing: Sparkline Data Structure

The plan says sparklines are "accumulated on the frontend from the SSE stream since page load." This works but means sparklines are ephemeral — lost on page refresh. If persistence is desired later, a `price_history` table would be needed. Worth noting as a known limitation.

## Minor Nits

- **§5**: `LLM_MOCK=false` is presented as optional but its type is string (`"true"`/`"false"`). Should note it's interpreted as a string, not a boolean environment variable.
- **§8**: `POST /api/portfolio/trade` uses `quantity` in request but `POST /api/chat` uses `quantity` in trades array — consistent, good.
- **§2**: "No login, no signup" is clean for a demo, but `user_id` columns exist in every table. A brief note explaining that single-user mode uses `"default"` and multi-user would be trivial later would be helpful.

## Summary

This is a solid, well-reasoned plan. The suggestions above are mostly about tightening ambiguities and filling gaps rather than fundamental disagreements. The most actionable items are:

1. Define the error envelope for all API endpoints
2. Pick the frontend charting library definitively
3. Clarify fractional share precision and watchlist validation
4. Specify the frontend state management approach
5. Acknowledge SSE scalability as a future consideration
