"""
costs.py
真实交易摩擦与市场冲击力模型 (RealisticTransactionCostModel)
包含券商佣金 (0.025%)、印花税 (0.05%)、买卖滑点与冲击力模型 (Impact ∝ sqrt(OrderSize / ADV))。
"""

import numpy as np
from typing import Dict, Any, Optional


class RealisticTransactionCostModel:
    def __init__(
        self,
        commission_rate: float = 0.00025,
        stamp_duty_rate: float = 0.0005,
        base_slippage: float = 0.0005,
        impact_coefficient: float = 0.10
    ):
        self.commission_rate = commission_rate
        self.stamp_duty_rate = stamp_duty_rate
        self.base_slippage = base_slippage
        self.impact_coefficient = impact_coefficient

    def calculate_cost(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        order_size: float,
        price: float,
        adv: float = 100000.0  # 日均成交量 (Average Daily Volume)
    ) -> Dict[str, float]:
        trade_value = order_size * price

        # 1. 佣金 (买卖均收，双向)
        commission = max(5.0, trade_value * self.commission_rate)

        # 2. 印花税 (仅卖出收取)
        stamp_duty = trade_value * self.stamp_duty_rate if side.upper() == "SELL" else 0.0

        # 3. 滑点与市场冲击力计算 (Impact ∝ sqrt(OrderSize / ADV))
        adv_ratio = min(1.0, order_size / max(1.0, adv))
        market_impact_pct = self.base_slippage + self.impact_coefficient * np.sqrt(adv_ratio)
        slippage_cost = trade_value * market_impact_pct

        total_cost = commission + stamp_duty + slippage_cost

        return {
            "commission": round(commission, 2),
            "stamp_duty": round(stamp_duty, 2),
            "slippage_cost": round(slippage_cost, 2),
            "total_cost": round(total_cost, 2),
            "cost_pct": round(total_cost / max(1.0, trade_value), 6)
        }
