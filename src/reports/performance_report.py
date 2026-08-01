"""
performance_report.py
统一策略与组合绩效评价报告生成模块 (PerformanceReport)
计算 CAGR, Sharpe, Sortino, MaxDrawdown, Volatility, Calmar, Turnover, TotalReturn。
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


class PerformanceReport:
    @staticmethod
    def calculate_metrics(history_df: pd.DataFrame, benchmark_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        if history_df is None or history_df.empty:
            return {
                "TotalReturn": 0.0, "CAGR": 0.0, "Sharpe": 0.0, "Sortino": 0.0,
                "MaxDrawdown": 0.0, "Volatility": 0.0, "Calmar": 0.0, "Turnover": 0.0
            }

        daily_returns = history_df["daily_return"].fillna(0.0)
        equity = history_df["equity"]
        initial_eq = float(equity.iloc[0])
        final_eq = float(equity.iloc[-1])
        total_return = (final_eq - initial_eq) / initial_eq

        num_days = len(history_df)
        years = num_days / 252.0 if num_days > 0 else 1.0

        cagr = (final_eq / initial_eq) ** (1.0 / years) - 1.0 if (years > 0 and final_eq > 0) else total_return

        volatility = float(daily_returns.std() * np.sqrt(252))

        # Sharpe (risk_free=0.0)
        sharpe = float((daily_returns.mean() / daily_returns.std()) * np.sqrt(252)) if daily_returns.std() > 0 else 0.0

        # Sortino (downside risk)
        downside_returns = daily_returns[daily_returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0.0
        sortino = float((daily_returns.mean() * 252) / downside_std) if downside_std > 0 else 0.0

        # Max Drawdown
        cum_max = equity.cummax()
        drawdown = (cum_max - equity) / cum_max
        max_drawdown = float(drawdown.max())

        # Calmar Ratio
        calmar = float(cagr / max_drawdown) if max_drawdown > 0 else 0.0

        bm_return = 0.0
        if benchmark_df is not None and not benchmark_df.empty:
            bm_close = benchmark_df["close"]
            bm_return = float((bm_close.iloc[-1] - bm_close.iloc[0]) / bm_close.iloc[0])

        return {
            "TotalReturn": round(total_return, 4),
            "TotalReturnPct": f"{total_return*100:.2f}%",
            "CAGR": round(cagr, 4),
            "CAGRPct": f"{cagr*100:.2f}%",
            "Sharpe": round(sharpe, 2),
            "Sortino": round(sortino, 2),
            "MaxDrawdown": round(max_drawdown, 4),
            "MaxDrawdownPct": f"{max_drawdown*100:.2f}%",
            "Volatility": round(volatility, 4),
            "VolatilityPct": f"{volatility*100:.2f}%",
            "Calmar": round(calmar, 2),
            "BenchmarkReturn": round(bm_return, 4),
            "BenchmarkReturnPct": f"{bm_return*100:.2f}%",
            "TradingDays": num_days
        }
