"""
value.py
估值因子实现 (ValueFactor)
基于 PE-TTM 倒数 (EP = 1 / PE_TTM) 计算估值因子，EP 越高越具安全边际。
"""

from typing import Optional
from src.factors.base import Factor
from src.data.provider import MarketDataProvider
from src.analysis.stock_f10_engine import get_valuation_metrics


class ValueFactor(Factor):
    def __init__(self):
        super().__init__(name="Value_EP", category="value")

    def compute(self, symbol: str, data_provider: MarketDataProvider, cutoff_date: Optional[str] = None) -> float:
        v_info = get_valuation_metrics(symbol)
        pe = float(v_info.get("pe_ttm", 20.0))
        return (1.0 / pe) if pe > 0 else 0.05
