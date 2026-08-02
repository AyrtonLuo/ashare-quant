"""
comparison.py — Multi-Strategy Comparison Engine & Benchmark Analytics.
"""

from dataclasses import dataclass
from typing import Dict, List
import numpy as np
from src.quant.backtest.engine import BacktestResult


@dataclass(frozen=True)
class BenchmarkComparisonResult:
    strategy_id: str
    benchmark_id: str
    active_return: float
    tracking_error: float
    information_ratio: float


class StrategyComparator:
    """Compares multiple strategy runs and benchmark relative analytics."""

    @staticmethod
    def compare_strategies(results: List[BacktestResult]) -> Dict[str, Dict[str, float]]:
        summary = {}
        for r in results:
            summary[r.strategy_id] = {
                "total_return": r.total_return,
                "annualized_return": r.annualized_return,
                "annualized_volatility": r.annualized_volatility,
                "sharpe_ratio": r.sharpe_ratio,
                "max_drawdown": r.max_drawdown,
                "win_rate": r.win_rate,
                "turnover": r.turnover
            }
        return summary

    @staticmethod
    def compare_against_benchmark(
        strategy_result: BacktestResult,
        benchmark_returns: List[float],
        benchmark_id: str = "equal_weight_benchmark"
    ) -> BenchmarkComparisonResult:
        s_returns = np.array(strategy_result.daily_returns)
        b_returns = np.array(benchmark_returns[:len(s_returns)])

        active_ret = float((np.mean(s_returns) - np.mean(b_returns)) * 252.0)
        diff = s_returns - b_returns
        tracking_error = float(np.std(diff) * np.sqrt(252.0))
        info_ratio = float(active_ret / (tracking_error + 1e-8))

        return BenchmarkComparisonResult(
            strategy_id=strategy_result.strategy_id,
            benchmark_id=benchmark_id,
            active_return=round(active_ret, 4),
            tracking_error=round(tracking_error, 4),
            information_ratio=round(info_ratio, 4)
        )
