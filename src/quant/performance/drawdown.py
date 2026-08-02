"""
drawdown.py — Drawdown Analytics Engine (Start, Bottom, Recovery Date, Recovery Duration).
"""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np


@dataclass(frozen=True)
class DrawdownAnalysisResult:
    max_drawdown_pct: float
    start_date: Optional[str]
    bottom_date: Optional[str]
    recovery_date: Optional[str]   # None if unrecovered
    recovery_days: Optional[int]


class DrawdownAnalytics:
    """Calculates Max Drawdown Peak, Trough, and Recovery Duration."""

    @staticmethod
    def analyze_drawdown(
        equity_curve: List[float], trading_dates: List[str]
    ) -> DrawdownAnalysisResult:
        if not equity_curve or len(equity_curve) != len(trading_dates):
            return DrawdownAnalysisResult(0.0, None, None, None, None)

        arr = np.array(equity_curve)
        peaks = np.maximum.accumulate(arr)
        drawdowns = (peaks - arr) / peaks

        max_dd_idx = int(np.argmax(drawdowns))
        max_dd_val = float(drawdowns[max_dd_idx])

        if max_dd_val == 0:
            return DrawdownAnalysisResult(0.0, None, None, None, None)

        bottom_date = trading_dates[max_dd_idx]

        # Peak date before max drawdown bottom
        peak_val = peaks[max_dd_idx]
        start_idx = int(np.where(arr[:max_dd_idx] == peak_val)[0][0]) if max_dd_idx > 0 else 0
        start_date = trading_dates[start_idx]

        # Recovery date after max drawdown bottom
        recovery_date = None
        recovery_days = None
        for i in range(max_dd_idx + 1, len(arr)):
            if arr[i] >= peak_val:
                recovery_date = trading_dates[i]
                recovery_days = i - start_idx
                break

        return DrawdownAnalysisResult(
            max_drawdown_pct=round(max_dd_val, 4),
            start_date=start_date,
            bottom_date=bottom_date,
            recovery_date=recovery_date,
            recovery_days=recovery_days
        )
