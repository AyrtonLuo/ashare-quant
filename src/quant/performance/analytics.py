"""
analytics.py — Performance Analytics Calculation Engine.
"""

from typing import List, Dict, Any
import numpy as np


class PerformanceAnalytics:
    """Calculates Sharpe Ratio, Max Drawdown, Annualized Volatility and Returns."""

    @staticmethod
    def calculate_sharpe(daily_returns: List[float], risk_free_rate: float = 0.02) -> float:
        if not daily_returns:
            return 0.0
        arr = np.array(daily_returns)
        ann_ret = float(np.mean(arr) * 252.0)
        ann_vol = float(np.std(arr) * np.sqrt(252.0))
        return float((ann_ret - risk_free_rate) / (ann_vol + 1e-8))

    @staticmethod
    def calculate_max_drawdown(equity_curve: List[float]) -> float:
        if not equity_curve:
            return 0.0
        arr = np.array(equity_curve)
        peaks = np.maximum.accumulate(arr)
        drawdowns = (peaks - arr) / peaks
        return float(np.max(drawdowns))
