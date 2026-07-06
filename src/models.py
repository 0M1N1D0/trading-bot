"""Tipos de datos compartidos por todo el bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RuleType(str, Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PCT_CHANGE = "pct_change"


@dataclass(frozen=True)
class AlertRule:
    type: RuleType
    value: float

    def key(self) -> str:
        """Identificador estable de esta regla, usado para dedup en state.py."""
        return f"{self.type.value}:{self.value}"


@dataclass(frozen=True)
class WatchItem:
    ticker: str
    market: str  # "US" o "MX"
    interval: str
    rules: list[AlertRule] = field(default_factory=list)


@dataclass(frozen=True)
class Quote:
    ticker: str
    price: float
    prev_close: float
    timestamp: datetime

    @property
    def pct_change(self) -> float:
        if not self.prev_close:
            return 0.0
        return (self.price - self.prev_close) / self.prev_close * 100
