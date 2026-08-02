"""
market_data.py — Canonical Market Data Contract for China A-Shares.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class MarketDataContract:
    symbol: str               # e.g., "600519.SH", "000001.SZ"
    timestamp: datetime       # UTC ISO 8601 or Local datetime
    trading_date: str         # "YYYY-MM-DD"
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float             # Shares traded
    amount: float             # Currency amount traded (RMB)
    adj_factor: float         # Cumulative corporate action multiplier
    unadjusted_close: float
    trading_status: str       # "NORMAL", "SUSPENDED", "HALTED"
    quality_status: str       # "VALID", "INVALID", "SUSPECT", "MISSING", "STALE"

    def __post_init__(self):
        if not self.symbol or "." not in self.symbol:
            raise ValueError(f"Invalid symbol format: {self.symbol}. Expected format '600519.SH'")
        if self.high_price < self.low_price:
            raise ValueError(f"Invalid price bounds: high ({self.high_price}) < low ({self.low_price})")
