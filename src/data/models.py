"""
models.py
统一行情数据模型 (MarketData)
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class MarketData:
    symbol: str
    timestamp: str  # YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    amount: float = 0.0
    change_pct: float = 0.0
    name: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "amount": self.amount,
            "change_pct": self.change_pct,
            "name": self.name
        }
