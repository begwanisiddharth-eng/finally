"""Structured output schema parsing and validation tests."""

import pytest
from pydantic import ValidationError

from app.llm.schema import ChatResponse, TradeAction


def test_parse_full_response():
    raw = (
        '{"message":"Done","trades":[{"ticker":"AAPL","side":"buy","quantity":10}],'
        '"watchlist_changes":[{"ticker":"PYPL","action":"add"}]}'
    )
    r = ChatResponse.model_validate_json(raw)
    assert r.message == "Done"
    assert r.trades[0].ticker == "AAPL"
    assert r.watchlist_changes[0].action == "add"


def test_optional_lists_default_empty():
    r = ChatResponse.model_validate_json('{"message":"hi"}')
    assert r.trades == []
    assert r.watchlist_changes == []


def test_quantity_must_be_positive():
    with pytest.raises(ValidationError):
        TradeAction(ticker="AAPL", side="buy", quantity=0)


def test_quantity_min_fraction():
    with pytest.raises(ValidationError):
        TradeAction(ticker="AAPL", side="buy", quantity=0.0001)
    # 0.001 is the allowed minimum.
    assert TradeAction(ticker="AAPL", side="buy", quantity=0.001).quantity == 0.001


def test_invalid_side_rejected():
    with pytest.raises(ValidationError):
        TradeAction(ticker="AAPL", side="hold", quantity=1)


def test_malformed_json_raises():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate_json('{"message": ')
