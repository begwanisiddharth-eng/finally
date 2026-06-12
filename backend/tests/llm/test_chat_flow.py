"""End-to-end chat flow tests against a real temp DB + cache.

Mock mode (LLM_MOCK=true) exercises the real trade/watchlist execution path.
Non-mock tests patch the LiteLLM completion call.
"""

from __future__ import annotations

import pytest

from app.db import (
    get_cash_balance,
    list_positions,
    list_recent_chat_messages,
    list_watchlist,
)
from app.llm import service
from app.llm.schema import ChatResponse, TradeAction, WatchlistAction


@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")


async def test_mock_buy_executes(conn, cache, source, mock_mode):
    result = await service.handle_chat(conn, cache, source, "buy 10 AAPL")

    assert result["message"] == "[MOCK] Executing: buy 10 AAPL."
    assert result["trades"] == [{"ticker": "AAPL", "side": "buy", "quantity": 10.0}]
    assert result["trade_results"][0]["ok"] is True
    assert result["trade_results"][0]["price"] == 190.0

    positions = await list_positions(conn)
    assert positions[0]["ticker"] == "AAPL"
    assert positions[0]["quantity"] == 10.0
    assert await get_cash_balance(conn) == pytest.approx(10000.0 - 10 * 190.0)


async def test_mock_buy_insufficient_cash_reports_error(conn, cache, source, mock_mode):
    # 1000 * 190 = 190k > 10k cash.
    result = await service.handle_chat(conn, cache, source, "buy 1000 AAPL")

    assert result["trade_results"][0]["ok"] is False
    assert result["trade_results"][0]["error"] == "Insufficient cash"
    assert await list_positions(conn) == []
    assert await get_cash_balance(conn) == 10000.0


async def test_mock_watchlist_add_executes(conn, cache, source, mock_mode):
    result = await service.handle_chat(conn, cache, source, "watch PYPL")

    assert result["watchlist_changes"] == [{"ticker": "PYPL", "action": "add"}]
    assert result["watchlist_results"][0]["ok"] is True
    assert "PYPL" in await list_watchlist(conn)
    assert "PYPL" in source.added


async def test_mock_persists_user_and_assistant_messages(conn, cache, source, mock_mode):
    await service.handle_chat(conn, cache, source, "buy 1 AAPL")

    messages = await list_recent_chat_messages(conn)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "buy 1 AAPL"
    assert messages[0]["actions"] is None
    # Assistant message carries the structured actions JSON.
    actions = messages[1]["actions"]
    assert actions["trades"] == [{"ticker": "AAPL", "side": "buy", "quantity": 1.0}]
    assert actions["trade_results"][0]["ok"] is True


async def test_mock_plain_message_no_actions(conn, cache, source, mock_mode):
    result = await service.handle_chat(conn, cache, source, "how am I doing?")
    assert result["trades"] == []
    assert result["watchlist_changes"] == []
    assert result["trade_results"] == []
    assert result["watchlist_results"] == []


async def test_real_path_calls_llm_and_executes(conn, cache, source, monkeypatch):
    """Non-mock path: patch the LLM call, verify auto-execution + history use."""
    monkeypatch.delenv("LLM_MOCK", raising=False)
    captured = {}

    async def fake_call_llm(messages):
        captured["messages"] = messages
        return ChatResponse(
            message="Bought it.",
            trades=[TradeAction(ticker="TSLA", side="buy", quantity=2)],
            watchlist_changes=[WatchlistAction(ticker="NVDA", action="remove")],
        )

    monkeypatch.setattr(service, "call_llm", fake_call_llm)
    result = await service.handle_chat(conn, cache, source, "buy 2 TSLA, drop NVDA")

    assert result["message"] == "Bought it."
    assert result["trade_results"][0]["ok"] is True
    assert result["watchlist_results"][0]["ok"] is True
    # Context block was assembled and passed as a system message.
    assert any("PORTFOLIO CONTEXT" in m["content"] for m in captured["messages"])
    assert captured["messages"][-1]["content"] == "buy 2 TSLA, drop NVDA"


async def test_real_path_history_passed_to_llm(conn, cache, source, monkeypatch):
    monkeypatch.delenv("LLM_MOCK", raising=False)

    async def first_call(messages):
        return ChatResponse(message="hi there")

    monkeypatch.setattr(service, "call_llm", first_call)
    await service.handle_chat(conn, cache, source, "hello")

    captured = {}

    async def second_call(messages):
        captured["messages"] = messages
        return ChatResponse(message="again")

    monkeypatch.setattr(service, "call_llm", second_call)
    await service.handle_chat(conn, cache, source, "hello again")

    contents = [m["content"] for m in captured["messages"]]
    assert "hello" in contents  # prior user turn
    assert "hi there" in contents  # prior assistant turn
