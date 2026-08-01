"""
position.py
持仓数据模型 (Position)
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Position:
    symbol: str
    quantity: int = 0
    available_quantity: int = 0
    average_cost: float = 0.0
    market_price: float = 0.0
    name: str = ""

    @property
    def market_value(self) -> float:
        return float(self.quantity * self.market_price)

    @property
    def unrealized_pnl(self) -> float:
        return float((self.market_price - self.average_cost) * self.quantity)

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.average_cost > 0:
            return float(((self.market_price - self.average_cost) / self.average_cost) * 100.0)
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "quantity": self.quantity,
            "available_quantity": self.available_quantity,
            "frozen_quantity": self.quantity - self.available_quantity,
            "average_cost": round(self.average_cost, 4),
            "market_price": round(self.market_price, 4),
            "market_value": round(self.market_value, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 2)
        }
