"""
quality.py
质量因子实现 (QualityFactor)
基于 PB 与 PE 之比或 ROE 代理计算质量因子。
"""

from typing import Optional
from src.factors.base import Factor
from src.data.provider import MarketDataProvider
from src.analysis.stock_f10_engine import get_valuation_metrics


class QualityFactor(Factor):
    def __init__(self):
        super().__init__(name="Quality_ROE", category="quality")

    def compute(self, symbol: str, data_provider: MarketDataProvider, cutoff_date: Optional[str] = None) -> float:
        v_info = get_valuation_metrics(symbol)
        pb = float(v_info.get("pb", 3.0))
        pe = float(v_info.get("pe_ttm", 20.0))
        roe = (pb / pe) if pe > 0 else 0.15
        return float(roe)
