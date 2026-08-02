"""
cost_model.py — A-Share Transaction Cost & Slippage Simulation Model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TransactionCostModel:
    commission_rate: float = 0.00025   # 0.025% commission
    stamp_duty_rate: float = 0.0005    # 0.05% sell-side stamp duty
    slippage_rate: float = 0.0001      # 0.01% slippage
    cost_model_version: str = "1.0.0"

    def calculate_trade_cost(self, trade_amount: float, is_buy: bool) -> float:
        comm = trade_amount * self.commission_rate
        slip = trade_amount * self.slippage_rate
        stamp = 0.0 if is_buy else (trade_amount * self.stamp_duty_rate)
        return comm + slip + stamp
