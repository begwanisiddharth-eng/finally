"""Chat orchestration: context -> LLM -> auto-execute -> persist -> respond."""

from __future__ import annotations

import os

import aiosqlite

from app.db import insert_chat_message, list_recent_chat_messages
from app.market import MarketDataSource, PriceCache
from app.services.trades import TradeError, execute_trade
from app.services.watchlist import WatchlistError, execute_watchlist_change

from .client import call_llm
from .mock import mock_response
from .prompt import build_messages, format_portfolio_context
from .schema import ChatResponse

HISTORY_LIMIT = 20


def _mock_enabled() -> bool:
    return os.getenv("LLM_MOCK", "").lower() == "true"


async def _load_context(conn: aiosqlite.Connection, cache: PriceCache) -> str:
    """Build the portfolio + watchlist context block from the current state."""
    from app.api.watchlist import get_watchlist as _build_watchlist
    from app.services.portfolio import build_portfolio

    portfolio = await build_portfolio(conn, cache)
    watchlist = await _build_watchlist(conn, cache)
    return format_portfolio_context(
        cash_balance=portfolio["cash_balance"],
        total_value=portfolio["total_value"],
        positions=portfolio["positions"],
        watchlist=watchlist,
    )


async def _execute_trades(
    conn: aiosqlite.Connection, cache: PriceCache, response: ChatResponse
) -> list[dict]:
    """Run each requested trade through the shared trade service."""
    results = []
    for trade in response.trades:
        try:
            result = await execute_trade(conn, cache, trade.ticker, trade.side, trade.quantity)
            results.append(
                {
                    "ticker": result["ticker"],
                    "side": result["side"],
                    "quantity": result["quantity"],
                    "price": result["price"],
                    "ok": True,
                }
            )
        except TradeError as exc:
            results.append(
                {
                    "ticker": trade.ticker.upper(),
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "ok": False,
                    "error": str(exc),
                }
            )
    return results


async def _execute_watchlist_changes(
    conn: aiosqlite.Connection, source: MarketDataSource, response: ChatResponse
) -> list[dict]:
    """Run each watchlist change through the shared watchlist service."""
    results = []
    for change in response.watchlist_changes:
        try:
            results.append(
                await execute_watchlist_change(conn, source, change.ticker, change.action)
            )
        except WatchlistError as exc:
            results.append(
                {
                    "ticker": change.ticker.upper(),
                    "action": change.action,
                    "ok": False,
                    "error": str(exc),
                }
            )
    return results


async def handle_chat(
    conn: aiosqlite.Connection,
    cache: PriceCache,
    source: MarketDataSource,
    user_message: str,
) -> dict:
    """Full chat flow. Returns the PLAN.md section 8 response shape."""
    context = await _load_context(conn, cache)
    history = await list_recent_chat_messages(conn, limit=HISTORY_LIMIT)

    if _mock_enabled():
        response = mock_response(user_message)
    else:
        messages = build_messages(context, history, user_message)
        response = call_llm(messages)

    trade_results = await _execute_trades(conn, cache, response)
    watchlist_results = await _execute_watchlist_changes(conn, source, response)

    await insert_chat_message(conn, "user", user_message)
    actions = {
        "trades": [t.model_dump() for t in response.trades],
        "watchlist_changes": [w.model_dump() for w in response.watchlist_changes],
        "trade_results": trade_results,
        "watchlist_results": watchlist_results,
    }
    await insert_chat_message(conn, "assistant", response.message, actions=actions)

    return {
        "message": response.message,
        "trades": [t.model_dump() for t in response.trades],
        "watchlist_changes": [w.model_dump() for w in response.watchlist_changes],
        "trade_results": trade_results,
        "watchlist_results": watchlist_results,
    }
