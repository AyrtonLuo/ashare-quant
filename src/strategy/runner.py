"""
runner.py
统一策略执行器 (StrategyRunner)
统一管理 Market Data -> Strategy -> StrategySignal -> Risk Check -> Target Portfolio 流程。
支持调仓频率 (daily, weekly, monthly) 控制。
"""

import logging
import pandas as pd
from typing import Optional, Dict, Any, Tuple
from src.strategy.interface import Strategy
from src.strategy.signal import StrategySignal
from src.strategy.risk_engine import DynamicCapitalAllocator
from src.data.provider import MarketDataProvider

logger = logging.getLogger("strategy_runner")


class StrategyRunner:
    def __init__(
        self,
        strategy: Strategy,
        data_provider: MarketDataProvider,
        risk_allocator: Optional[DynamicCapitalAllocator] = None,
        rebalance_frequency: str = "daily"  # "daily", "weekly", "monthly"
    ):
        self.strategy = strategy
        self.data_provider = data_provider
        self.risk_allocator = risk_allocator or DynamicCapitalAllocator()
        self.rebalance_frequency = rebalance_frequency.lower()
        self.last_signal: Optional[StrategySignal] = None
        self.last_rebalance_date: Optional[str] = None

    def is_rebalance_date(self, current_date: str) -> bool:
        """根据配置的调仓频率判定当前日期是否触发调仓"""
        if self.last_rebalance_date is None:
            return True
        if self.rebalance_frequency == "daily":
            return True

        curr_dt = pd.to_datetime(current_date)
        last_dt = pd.to_datetime(self.last_rebalance_date)

        if self.rebalance_frequency == "weekly":
            return (curr_dt - last_dt).days >= 7 or curr_dt.weekday() < last_dt.weekday()
        elif self.rebalance_frequency == "monthly":
            return curr_dt.month != last_dt.month or curr_dt.year != last_dt.year

        return True

    def run_step(
        self,
        timestamp: str,
        portfolio_state: Optional[Dict[str, Any]] = None,
        market_override: Optional[Dict[str, Any]] = None
    ) -> Tuple[StrategySignal, pd.DataFrame, Dict[str, Any]]:
        """
        单步运行调仓逻辑：
        返回: (signal, target_portfolio_df, market_regime)
        """
        if self.risk_allocator:
            regime = self.risk_allocator.evaluate_market_regime()
        else:
            regime = {
                "regime": "🟢 正常看多",
                "equity_cap_pct": 100.0,
                "cash_reserve_pct": 0.0,
                "max_single_stock_pct": 100.0,
                "advice": "无大盘限制"
            }

        if not self.is_rebalance_date(timestamp) and self.last_signal is not None:
            sig = self.last_signal
        else:
            sig = self.strategy.generate_signal(
                data_provider=self.data_provider,
                portfolio_state=portfolio_state,
                timestamp=timestamp
            )
            self.last_signal = sig
            self.last_rebalance_date = timestamp

        target_df = sig.to_dataframe()
        if not target_df.empty:
            target_df["target_weight_pct"] = target_df["target_weight"] * 100.0

        return sig, target_df, regime
