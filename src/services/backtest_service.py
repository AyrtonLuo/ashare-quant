"""
backtest_service.py
历史回测服务层 (BacktestService)
隔离 BacktestEngine2 与报告逻辑，为 UI 提供纯粹的回测运行与结果封装。
"""

import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from src.strategy.interface import Strategy
from src.data.provider import MarketDataProvider
from src.backtest_engine_v2 import BacktestEngine2
from src.strategy.risk_engine import DynamicCapitalAllocator


class BacktestService:
    def __init__(self, data_provider: MarketDataProvider):
        self.data_provider = data_provider

    def run_backtest(
        self,
        strategy: Strategy,
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 1000000.0,
        rebalance_frequency: str = "daily",
        benchmark_symbol: Optional[str] = "000300"
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        engine = BacktestEngine2(
            strategy=strategy,
            data_provider=self.data_provider,
            initial_capital=initial_capital,
            rebalance_frequency=rebalance_frequency
        )
        hist_df, perf, _ = engine.run(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            benchmark_symbol=benchmark_symbol
        )
        return hist_df, perf
