"""
liquidity.py
流动性因子实现 (LiquidityFactor)
计算 N 日平均换手率 / 成交量
"""

from typing import Optional
from src.factors.base import Factor
from src.data.provider import MarketDataProvider


class LiquidityFactor(Factor):
    def __init__(self, window: int = 20):
        super().__init__(name=f"Liquidity_{window}D", category="liquidity")
        self.window = window

    def compute(self, symbol: str, data_provider: MarketDataProvider, cutoff_date: Optional[str] = None) -> float:
        df = data_provider.get_history(symbol, end_date=cutoff_date)
        if df is None or len(df) < self.window:
            return 0.0
        vol = df['volume'].values[-self.window:]
        return float(vol.mean()) if len(vol) > 0 else 0.0
