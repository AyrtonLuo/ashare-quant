"""
benchmark.py — Equal Weight Benchmark Simulation Engine.
"""

from typing import List, Dict


class EqualWeightBenchmark:
    """Simulates an equal-weight buy-and-hold benchmark for universe equity comparison."""

    @staticmethod
    def calculate_benchmark_equity(
        daily_prices: Dict[str, List[float]], initial_capital: float = 1000000.0
    ) -> List[float]:
        num_days = min([len(p) for p in daily_prices.values()]) if daily_prices else 0
        equity = initial_capital
        equity_curve = [equity]

        for i in range(1, num_days):
            day_ret = 0.0
            for symbol, prices in daily_prices.items():
                p_prev = prices[i - 1]
                p_curr = prices[i]
                ret = (p_curr - p_prev) / p_prev if p_prev > 0 else 0.0
                day_ret += (ret / len(daily_prices))
            equity *= (1.0 + day_ret)
            equity_curve.append(round(equity, 2))

        return equity_curve
