"""
backtest_engine_v2.py
Phase 3 统一架构向量化回测引擎 (BacktestEngine2)
基于 Strategy -> StrategySignal -> Risk Check -> Portfolio Engine 2.0 统一主流程。
共享 TransactionCostModel、支持无未来函数数据切片、支持调仓频率与基准比对。
"""

import os
import logging
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

from src.strategy.interface import Strategy
from src.strategy.runner import StrategyRunner
from src.strategy.risk_engine import DynamicCapitalAllocator
from src.data.provider import MarketDataProvider
from src.portfolio.portfolio import Portfolio
from src.portfolio.order import Order, OrderSide, OrderStatus
from src.portfolio.history import PortfolioHistory
from src.reports.performance_report import PerformanceReport
from src.reports.decision_logger import DecisionAuditLog

logger = logging.getLogger("backtest_engine_v2")


class SlicedMarketDataProvider(MarketDataProvider):
    """
    防未来函数数据切片 Provider (SlicedMarketDataProvider)
    仅向 Strategy 提供小于等于 cutoff_date 的历史数据，彻底切割未来价格与未来信息。
    """
    def __init__(self, full_provider: MarketDataProvider, cutoff_date: str):
        self.full_provider = full_provider
        self.cutoff_date = cutoff_date

    def get_latest(self, symbol: str):
        df = self.get_history(symbol)
        if not df.empty:
            last = df.iloc[-1]
            from src.data.models import MarketData
            return MarketData(
                symbol=symbol,
                timestamp=str(last['date'])[:10],
                open=float(last.get('open', last['close'])),
                high=float(last.get('high', last['close'])),
                low=float(last.get('low', last['close'])),
                close=float(last['close']),
                volume=float(last.get('volume', 0.0))
            )
        return self.full_provider.get_latest(symbol)

    def get_history(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        effective_end = self.cutoff_date
        if end_date and end_date < effective_end:
            effective_end = end_date
        return self.full_provider.get_history(symbol, start_date=start_date, end_date=effective_end)

    def get_daily(self, symbols: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        return {sym: self.get_history(sym, start_date=start_date, end_date=end_date) for sym in symbols}


class BacktestEngine2:
    def __init__(
        self,
        strategy: Strategy,
        data_provider: MarketDataProvider,
        initial_capital: float = 100000.0,
        rebalance_frequency: str = "daily",
        risk_allocator: Optional[DynamicCapitalAllocator] = None,
        enable_audit_log: bool = False
    ):
        self.strategy = strategy
        self.data_provider = data_provider
        self.initial_capital = initial_capital
        self.rebalance_frequency = rebalance_frequency
        self.risk_allocator = risk_allocator
        self.enable_audit_log = enable_audit_log

    def run(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        benchmark_symbol: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any], PortfolioHistory]:
        """
        运行 Phase 3 统一架构历史回测
        """
        portfolio = Portfolio(initial_capital=self.initial_capital)
        history = PortfolioHistory()
        decision_logger = DecisionAuditLog() if self.enable_audit_log else None

        first_sym = symbols[0]
        calendar_df = self.data_provider.get_history(first_sym, start_date=start_date, end_date=end_date)
        if calendar_df.empty:
            raise ValueError(f"未找到标的 {first_sym} 在 {start_date} ~ {end_date} 的历史交易数据")

        trading_dates = [str(d)[:10] for d in calendar_df['date'].tolist()]
        runner = StrategyRunner(
            strategy=self.strategy,
            data_provider=self.data_provider,
            risk_allocator=self.risk_allocator,
            rebalance_frequency=self.rebalance_frequency
        )

        for date_str in trading_dates:
            sliced_provider = SlicedMarketDataProvider(self.data_provider, cutoff_date=date_str)
            runner.data_provider = sliced_provider

            current_prices = {}
            for sym in symbols:
                h_df = sliced_provider.get_history(sym)
                if not h_df.empty:
                    current_prices[sym] = float(h_df['close'].iloc[-1])

            before_summary = portfolio.get_summary(current_prices)

            if runner.is_rebalance_date(date_str):
                sig, target_df, regime = runner.run_step(timestamp=date_str, portfolio_state=before_summary)
                target_weights = sig.target_weights

                allowed_equity = before_summary["total_equity"] * (regime.get("equity_cap_pct", 100.0) / 100.0)
                orders_this_step = []

                for sym in list(portfolio.positions.keys()):
                    pos = portfolio.positions[sym]
                    usable = pos.available_quantity
                    if pos.quantity <= 0:
                        continue
                    p = current_prices.get(sym, pos.average_cost)
                    w = target_weights.get(sym, 0.0)
                    t_val = allowed_equity * w
                    t_shares = int((t_val // (p * 100)) * 100) if p > 0 else 0

                    if pos.quantity > t_shares:
                        sell_req = pos.quantity - t_shares
                        actual_sell = min(sell_req, usable)
                        actual_sell = (actual_sell // 100) * 100
                        if actual_sell > 0:
                            order = Order(symbol=sym, side=OrderSide.SELL, quantity=actual_sell, price=p)
                            exec_o = portfolio.submit_order(order)
                            if exec_o.status == OrderStatus.FILLED:
                                orders_this_step.append(exec_o.to_dict())

                for sym, w in target_weights.items():
                    if w <= 0:
                        continue
                    p = current_prices.get(sym, 10.0)
                    t_val = allowed_equity * w
                    t_shares = int((t_val // (p * 100)) * 100) if p > 0 else 0

                    curr_pos = portfolio.positions.get(sym, None)
                    curr_shares = curr_pos.quantity if curr_pos else 0

                    if t_shares > curr_shares:
                        buy_req = t_shares - curr_shares
                        buy_req = (buy_req // 100) * 100
                        if buy_req > 0:
                            order = Order(symbol=sym, side=OrderSide.BUY, quantity=buy_req, price=p)
                            exec_o = portfolio.submit_order(order)
                            if exec_o.status == OrderStatus.FILLED:
                                orders_this_step.append(exec_o.to_dict())

                after_summary = portfolio.get_summary(current_prices)
                if decision_logger and orders_this_step:
                    decision_logger.log_decision(
                        timestamp=date_str,
                        strategy_id=self.strategy.strategy_id,
                        target_weights=target_weights,
                        risk_info=regime,
                        orders=orders_this_step,
                        portfolio_before=before_summary,
                        portfolio_after=after_summary
                    )

            portfolio.unfreeze_t1()
            summary = portfolio.get_summary(current_prices)
            history.record_step(
                timestamp=date_str,
                cash=summary["cash"],
                market_value=summary["market_value"],
                equity=summary["equity"]
            )

        history_df = history.to_dataframe()
        bm_df = None
        if benchmark_symbol:
            bm_df = self.data_provider.get_history(benchmark_symbol, start_date=start_date, end_date=end_date)

        perf_report = PerformanceReport.calculate_metrics(history_df, bm_df)
        return history_df, perf_report, history
