"""
order.py
订单模型与状态定义 (Order, OrderSide, OrderStatus)
"""

from dataclasses import dataclass, field
from enum import Enum
import uuid
import pandas as pd
from typing import Dict, Any, Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    order_type: str = "LIMIT"
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: OrderStatus = OrderStatus.PENDING
    created_at: str = field(default_factory=lambda: pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))
    filled_quantity: int = 0
    filled_price: float = 0.0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value if isinstance(self.side, OrderSide) else str(self.side),
            "quantity": self.quantity,
            "price": self.price,
            "order_type": self.order_type,
            "status": self.status.value if isinstance(self.status, OrderStatus) else str(self.status),
            "created_at": self.created_at,
            "filled_quantity": self.filled_quantity,
            "filled_price": self.filled_price,
            "reason": self.reason
        }
