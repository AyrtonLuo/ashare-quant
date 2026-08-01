"""
accounting.py
统一账户核算引擎 (PortfolioAccounting)
确保资产守恒公式 Equity = Cash + Market Value 全程成立。
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class PortfolioAccounting:
    initial_capital: float = 1000000.0
    cash: float = 1000000.0
    realized_pnl: float = 0.0

    def calculate(self, positions_dict: Dict[str, Any], current_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        根据当前持仓字典与最新报价字典精细计算账户核算指标
        """
        tot_market_value = 0.0
        tot_unrealized_pnl = 0.0

        for sym, pos in positions_dict.items():
            if isinstance(pos, dict):
                qty = int(pos.get("shares", pos.get("quantity", 0)))
                cost = float(pos.get("cost_price", pos.get("average_cost", 0.0)))
            else:
                qty = int(pos.quantity)
                cost = float(pos.average_cost)

            p = float(current_prices.get(sym, cost))
            mv = qty * p
            unrealized = (p - cost) * qty
            tot_market_value += mv
            tot_unrealized_pnl += unrealized

        equity = self.cash + tot_market_value
        total_pnl = equity - self.initial_capital
        pnl_pct = (total_pnl / self.initial_capital * 100.0) if self.initial_capital > 0 else 0.0

        return {
            "initial_capital": round(self.initial_capital, 2),
            "cash": round(self.cash, 2),
            "market_value": round(tot_market_value, 2),
            "equity": round(equity, 2),
            "total_equity": round(equity, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(tot_unrealized_pnl, 2),
            "total_pnl": round(total_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "total_return_pct": round(pnl_pct, 2)
        }

