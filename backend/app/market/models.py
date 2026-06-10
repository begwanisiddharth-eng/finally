"""Data models for market data."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        """Absolute price change from previous update."""
        return round(self.price - self.previous_price, 2)

    @property
    def change_percent(self) -> float:
        """Percentage change from previous update."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 2)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat'."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self, session_open: float | None = None) -> dict:
        """Serialize for JSON / SSE transmission using spec wire field names."""
        ts = datetime.fromtimestamp(self.timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "ticker": self.ticker,
            "price": self.price,
            "prev_price": self.previous_price,
            "session_open": session_open if session_open is not None else self.price,
            "change_pct": self.change_percent,
            "direction": self.direction,
            "timestamp": ts,
        }
