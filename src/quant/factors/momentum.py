"""
momentum.py — Price Momentum Factor implementation (20D, 60D, 120D).
"""

from datetime import datetime
from typing import List
from src.quant.factors.base import BaseFactor, FactorValue, FactorStatus


class PriceMomentumFactor(BaseFactor):
    def __init__(self, window_days: int = 20):
        self.window_days = window_days

    @property
    def name(self) -> str:
        return f"momentum_{self.window_days}d"

    @property
    def version(self) -> str:
        return "1.0.0"

    def compute(self, symbol: str, prices: List[float], effective_date: str, as_of: datetime) -> FactorValue:
        if len(prices) < self.window_days:
            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                factor_version=self.version,
                raw_value=None,
                effective_date=effective_date,
                as_of=as_of,
                status=FactorStatus.INSUFFICIENT_HISTORY,
                quality_notes=f"Requires {self.window_days} prices, got {len(prices)}"
            )

        start_price = prices[-self.window_days]
        end_price = prices[-1]

        if start_price <= 0:
            return FactorValue(
                symbol=symbol,
                factor_name=self.name,
                factor_version=self.version,
                raw_value=None,
                effective_date=effective_date,
                as_of=as_of,
                status=FactorStatus.INVALID
            )

        mom_val = (end_price - start_price) / start_price
        return FactorValue(
            symbol=symbol,
            factor_name=self.name,
            factor_version=self.version,
            raw_value=float(mom_val),
            effective_date=effective_date,
            as_of=as_of,
            status=FactorStatus.VALID
        )
