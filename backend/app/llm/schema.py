"""Structured output schema for the LLM chat assistant.

Mirrors PLAN.md section 9: the model returns a conversational message plus
optional trades and watchlist changes that the chat service auto-executes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TradeAction(BaseModel):
    """A single trade the assistant wants to execute."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float = Field(ge=0.001)


class WatchlistAction(BaseModel):
    """A single watchlist add/remove the assistant wants to perform."""

    ticker: str
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    """The structured response returned by the LLM."""

    message: str
    trades: list[TradeAction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistAction] = Field(default_factory=list)
