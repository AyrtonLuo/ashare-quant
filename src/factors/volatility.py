"""
volatility.py
低波动率因子实现 (VolatilityFactor)
计算 N 日收益率标准差，倒数作为低波动因子得分 (Low Volatility)
"""

import numpy as np
from typing import Optional
from src.factors.base import Factor
from src.data.provider import MarketDataProvider


class VolatilityFactor(Factor):
    def __init__(self, window: int = 20):
        super().__init__(name=f"LowVol_{window}D", category="volatility")
        self.window = window

    def compute(self, symbol: str, data_provider: MarketDataProvider, cutoff_date: Optional[str] = None) -> float:
        df = data_provider.get_history(symbol, end_date=cutoff_date)
        if df is None or len(df) < self.window:
            return 0.0
        rets = df['close'].pct_change().dropna().values[-self.window:]
        vol = float(np.std(rets)) if len(rets) > 0 else 0.01
        return (1.0 / vol) if vol > 0 else 100.0
