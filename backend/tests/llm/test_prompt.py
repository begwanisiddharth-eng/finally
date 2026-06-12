"""Prompt assembly tests."""

from app.llm.prompt import SYSTEM_PROMPT, build_messages, format_portfolio_context


def test_system_prompt_identity():
    assert "FinAlly" in SYSTEM_PROMPT
    assert "trading assistant" in SYSTEM_PROMPT


def test_format_context_with_positions():
    ctx = format_portfolio_context(
        cash_balance=8500.0,
        total_value=11234.56,
        positions=[
            {
                "ticker": "AAPL",
                "quantity": 10,
                "avg_cost": 190.0,
                "current_price": 195.5,
                "unrealized_pnl": 55.0,
                "pnl_pct": 2.89,
            }
        ],
        watchlist=[{"ticker": "AAPL", "price": 195.5, "change_pct": 2.89}],
    )
    assert "$8,500.00" in ctx
    assert "AAPL" in ctx
    assert "+2.89%" in ctx


def test_format_context_empty():
    ctx = format_portfolio_context(10000.0, 10000.0, [], [])
    assert "(none)" in ctx


def test_build_messages_order():
    msgs = build_messages(
        context="CTX",
        history=[
            {"role": "user", "content": "earlier"},
            {"role": "assistant", "content": "reply"},
        ],
        user_message="now",
    )
    assert msgs[0]["role"] == "system"
    assert msgs[1]["content"] == "CTX"
    assert msgs[2]["content"] == "earlier"
    assert msgs[-1] == {"role": "user", "content": "now"}
