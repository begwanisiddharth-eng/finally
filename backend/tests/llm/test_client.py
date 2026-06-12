"""LLM client tests with the LiteLLM completion call mocked."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.llm import client


def _fake_response(content: str):
    """Mimic the litellm completion return shape: choices[0].message.content."""
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_call_llm_parses_structured_output(monkeypatch):
    raw = '{"message":"ok","trades":[{"ticker":"AAPL","side":"buy","quantity":5}]}'
    monkeypatch.setattr(client, "completion_with_backoff", lambda **kw: _fake_response(raw))

    result = client.call_llm([{"role": "user", "content": "buy"}])
    assert result.message == "ok"
    assert result.trades[0].ticker == "AAPL"


def test_call_llm_malformed_json_raises(monkeypatch):
    monkeypatch.setattr(
        client, "completion_with_backoff", lambda **kw: _fake_response("not json")
    )
    with pytest.raises(ValidationError):
        client.call_llm([{"role": "user", "content": "hi"}])


def test_call_llm_invalid_schema_raises(monkeypatch):
    # Valid JSON, but quantity violates the gt=0 constraint.
    raw = '{"message":"x","trades":[{"ticker":"AAPL","side":"buy","quantity":-1}]}'
    monkeypatch.setattr(client, "completion_with_backoff", lambda **kw: _fake_response(raw))
    with pytest.raises(ValidationError):
        client.call_llm([{"role": "user", "content": "hi"}])


def test_call_llm_passes_model_and_structured_format(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"message":"ok"}')

    monkeypatch.setattr(client, "completion_with_backoff", fake_completion)
    client.call_llm([{"role": "user", "content": "hi"}])

    assert captured["model"] == "groq/openai/gpt-oss-120b"
    assert captured["response_format"] is client.ChatResponse
    assert captured["reasoning_effort"] == "high"
