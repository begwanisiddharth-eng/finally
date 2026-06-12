"""LLM client tests with the (async) LiteLLM completion call mocked."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.llm import client


def _fake_response(content: str):
    """Mimic the litellm completion return shape: choices[0].message.content."""
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _patch_completion(monkeypatch, content: str, captured: dict | None = None):
    """Replace the async completion_with_backoff with a coroutine returning content."""

    async def fake_completion(**kwargs):
        if captured is not None:
            captured.update(kwargs)
        return _fake_response(content)

    monkeypatch.setattr(client, "completion_with_backoff", fake_completion)


async def test_call_llm_parses_structured_output(monkeypatch):
    raw = '{"message":"ok","trades":[{"ticker":"AAPL","side":"buy","quantity":5}]}'
    _patch_completion(monkeypatch, raw)

    result = await client.call_llm([{"role": "user", "content": "buy"}])
    assert result.message == "ok"
    assert result.trades[0].ticker == "AAPL"


async def test_call_llm_malformed_json_raises(monkeypatch):
    _patch_completion(monkeypatch, "not json")
    with pytest.raises(ValidationError):
        await client.call_llm([{"role": "user", "content": "hi"}])


async def test_call_llm_invalid_schema_raises(monkeypatch):
    # Valid JSON, but quantity violates the minimum-quantity constraint.
    raw = '{"message":"x","trades":[{"ticker":"AAPL","side":"buy","quantity":-1}]}'
    _patch_completion(monkeypatch, raw)
    with pytest.raises(ValidationError):
        await client.call_llm([{"role": "user", "content": "hi"}])


async def test_call_llm_passes_model_and_structured_format(monkeypatch):
    captured: dict = {}
    _patch_completion(monkeypatch, '{"message":"ok"}', captured)

    await client.call_llm([{"role": "user", "content": "hi"}])

    assert captured["model"] == "groq/openai/gpt-oss-120b"
    assert captured["response_format"] is client.ChatResponse
    assert captured["reasoning_effort"] == "high"
