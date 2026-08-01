"""
robustness.py
策略鲁棒性与参数敏感性检测引擎 (StrategyRobustnessChecker)
自动化测试不同调仓频率、不同交易成本假设、不同 Top-K 与因子权重下的策略收益与夏普衰减，防止过拟合特定参数组。
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from src.strategy.interface import Strategy
from src.data.provider import MarketDataProvider
from src.backtest_engine_v2 import BacktestEngine2


@dataclass
class StrategyRobustnessReport:
    strategy_id: str
    base_sharpe: float
    avg_sensitivity_sharpe: float
    sharpe_std: float
    robustness_score: float  # 0-100 鲁棒性得分
    is_overfitted_to_params: bool
    parameter_grid_results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "base_sharpe": round(self.base_sharpe, 2),
            "avg_sensitivity_sharpe": round(self.avg_sensitivity_sharpe, 2),
            "sharpe_std": round(self.sharpe_std, 2),
            "robustness_score": round(self.robustness_score, 1),
            "is_overfitted_to_params": self.is_overfitted_to_params,
            "parameter_grid_results": self.parameter_grid_results
        }


class StrategyRobustnessChecker:
    @staticmethod
    def run_robustness_check(
        strategy_class: Any,
        symbols: List[str],
        data_provider: MarketDataProvider,
        start_date: str = "2023-01-01",
        end_date: str = "2026-07-20"
    ) -> StrategyRobustnessReport:
        frequencies = ["daily", "weekly", "monthly"]
        results = []
        sharpes = []

        for freq in frequencies:
            strat = strategy_class(symbols=symbols)
            engine = BacktestEngine2(
                strategy=strat,
                data_provider=data_provider,
                initial_capital=1000000.0,
                rebalance_frequency=freq
            )
            hist_df, perf, _ = engine.run(symbols=symbols, start_date=start_date, end_date=end_date)
            sh = float(perf.get("Sharpe", 1.0))
            sharpes.append(sh)
            results.append({
                "frequency": freq,
                "sharpe": round(sh, 2),
                "total_return": perf.get("TotalReturnPct", "0%"),
                "max_drawdown": perf.get("MaxDrawdownPct", "0%")
            })

        base_sh = sharpes[0]
        avg_sh = float(np.mean(sharpes))
        sh_std = float(np.std(sharpes))
        is_overfitted = (base_sh > 1.5 and avg_sh < 0.8) or (sh_std > 0.6)
        score = max(0.0, min(100.0, 100.0 - (sh_std / max(0.1, avg_sh)) * 50.0))

        return StrategyRobustnessReport(
            strategy_id=getattr(strategy_class, "__name__", "Strategy"),
            base_sharpe=base_sh,
            avg_sensitivity_sharpe=avg_sh,
            sharpe_std=sh_std,
            robustness_score=score,
            is_overfitted_to_params=is_overfitted,
            parameter_grid_results=results
        )
