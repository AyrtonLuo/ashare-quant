"""
volatility.py — Realized Volatility Factor implementation.
"""

from datetime import datetime
from typing import List
import numpy as np
from src.quant.factors.base import BaseFactor, FactorValue, FactorStatus


class RealizedVolatilityFactor(BaseFactor):
    def __init__(self, window_days: int = 20):
        self.window_days = window_days

    @property
    def name(self) -> str:
        return f"volatility_{self.window_days}d"

    @property
    def version(self) -> str:
        return "1.0.0"

    def compute(self, symbol: str, prices: List[float], effective_date: str, as_of: datetime) -> FactorValue:
        if len(prices) < self.window_days + 1:
            return FactorValue(
                symbol=symbol, factor_name=self.name, factor_version=self.version,
                raw_value=None, effective_date=effective_date, as_of=as_of,
                status=FactorStatus.INSUFFICIENT_HISTORY
            )

        window_prices = np.array(prices[-(self.window_days + 1):])
        returns = np.diff(window_prices) / window_prices[:-1]
        vol = float(np.std(returns) * np.sqrt(252.0))

        return FactorValue(
            symbol=symbol, factor_name=self.name, factor_version=self.version,
            raw_value=vol, effective_date=effective_date, as_of=as_of,
            status=FactorStatus.VALID
        )
