"""Deterministic mock LLM used when LLM_MOCK=true.

No network call, no API key. The chat service routes here so E2E tests can
assert on stable outputs. Triggers are matched case-insensitively on the user
message. The mock only emits the structured intent (trades / watchlist_changes);
the chat service still runs them through the real execution path, so results
reflect actual portfolio state.

Documented triggers (for integration-tester):
  - "buy <N> <TICKER>"      -> trades: [{TICKER, buy, N}]
  - "sell <N> <TICKER>"     -> trades: [{TICKER, sell, N}]
  - "watch <TICKER>" / "add <TICKER>"   -> watchlist_changes: [{TICKER, add}]
  - "unwatch <TICKER>" / "remove <TICKER>" -> watchlist_changes: [{TICKER, remove}]
  - anything else            -> plain analytical message, no actions
"""

from __future__ import annotations

import re

from .schema import ChatResponse, TradeAction, WatchlistAction

# "buy 10 AAPL" / "sell 2.5 TSLA"
_TRADE_RE = re.compile(r"\b(buy|sell)\s+([0-9]+(?:\.[0-9]+)?)\s+([A-Za-z]{1,10})\b", re.IGNORECASE)
# "watch NVDA" / "add NVDA" / "unwatch NVDA" / "remove NVDA"
_WATCH_RE = re.compile(r"\b(watch|add|unwatch|remove)\s+([A-Za-z]{1,10})\b", re.IGNORECASE)


def mock_response(user_message: str) -> ChatResponse:
    """Return a deterministic ChatResponse for the given user message."""
    trades: list[TradeAction] = []
    watchlist_changes: list[WatchlistAction] = []

    for side, qty, ticker in _TRADE_RE.findall(user_message):
        trades.append(
            TradeAction(ticker=ticker.upper(), side=side.lower(), quantity=float(qty))
        )

    for verb, ticker in _WATCH_RE.findall(user_message):
        action = "remove" if verb.lower() in ("unwatch", "remove") else "add"
        watchlist_changes.append(WatchlistAction(ticker=ticker.upper(), action=action))

    if trades:
        summary = ", ".join(f"{t.side} {t.quantity:g} {t.ticker}" for t in trades)
        message = f"[MOCK] Executing: {summary}."
    elif watchlist_changes:
        summary = ", ".join(f"{w.action} {w.ticker}" for w in watchlist_changes)
        message = f"[MOCK] Updating watchlist: {summary}."
    else:
        message = "[MOCK] I am FinAlly running in mock mode. No actions taken."

    return ChatResponse(message=message, trades=trades, watchlist_changes=watchlist_changes)
