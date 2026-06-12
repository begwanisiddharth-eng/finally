"""Pydantic request/response models for the REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TradeRequest(BaseModel):
    """Body for POST /api/portfolio/trade."""

    ticker: str
    quantity: float = Field(gt=0)
    side: str  # "buy" or "sell"


class WatchlistAddRequest(BaseModel):
    """Body for POST /api/watchlist."""

    ticker: str
