"""
liquidity.py — Average Volume / Turnover Liquidity Factor implementation.
"""

from datetime import datetime
from typing import List
import numpy as np
from src.quant.factors.base import BaseFactor, FactorValue, FactorStatus


class AverageVolumeFactor(BaseFactor):
    def __init__(self, window_days: int = 20):
        self.window_days = window_days

    @property
    def name(self) -> str:
        return f"avg_volume_{self.window_days}d"

    @property
    def version(self) -> str:
        return "1.0.0"

    def compute(self, symbol: str, volumes: List[float], effective_date: str, as_of: datetime) -> FactorValue:
        if len(volumes) < self.window_days:
            return FactorValue(
                symbol=symbol, factor_name=self.name, factor_version=self.version,
                raw_value=None, effective_date=effective_date, as_of=as_of,
                status=FactorStatus.INSUFFICIENT_HISTORY
            )

        avg_vol = float(np.mean(volumes[-self.window_days:]))
        return FactorValue(
            symbol=symbol, factor_name=self.name, factor_version=self.version,
            raw_value=avg_vol, effective_date=effective_date, as_of=as_of,
            status=FactorStatus.VALID
        )
