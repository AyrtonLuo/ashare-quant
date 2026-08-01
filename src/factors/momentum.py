"""
momentum.py
动量因子实现 (MomentumFactor)
计算 N 日价格动量收益率 (Close_t / Close_{t-N} - 1.0)
"""

import pandas as pd
from typing import Optional
from src.factors.base import Factor
from src.data.provider import MarketDataProvider


class MomentumFactor(Factor):
    def __init__(self, window: int = 20):
        super().__init__(name=f"Momentum_{window}D", category="momentum")
        self.window = window

    def compute(self, symbol: str, data_provider: MarketDataProvider, cutoff_date: Optional[str] = None) -> float:
        df = data_provider.get_history(symbol, end_date=cutoff_date)
        if df is None or len(df) < self.window:
            return 0.0
        close = df['close'].values
        p_now = close[-1]
        p_prev = close[-self.window]
        return float((p_now - p_prev) / p_prev) if p_prev > 0 else 0.0
