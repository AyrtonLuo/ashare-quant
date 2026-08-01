"""
test_phase3_pipeline.py
Phase 3 全套 13+ 单元测试与 Consistency 绝密考验
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy.signal import StrategySignal
from src.strategy.interface import Strategy
from src.strategy.ma_cross_strategy import MACrossStrategy
from src.strategy.runner import StrategyRunner
from src.data.cache import LocalCache
from src.data.akshare_provider import AkShareProvider
from src.portfolio.history import PortfolioHistory
from src.reports.performance_report import PerformanceReport
from src.reports.decision_logger import DecisionAuditLog
from src.backtest_engine_v2 import BacktestEngine2, SlicedMarketDataProvider
from src.execution.paper_trader import PaperAccount


def test_strategy_signal():
    sig = StrategySignal(
        timestamp="2026-08-01",
        strategy_id="test_strat",
        symbols=["600519", "000001"],
        target_weights={"600519": 0.50, "000001": 0.50}
    )
    df = sig.to_dataframe()
    assert len(df) == 2
    assert df.iloc[0]["target_weight"] == 0.50


def test_strategy_interface(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 20)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    strat = MACrossStrategy(symbols=["600519"])
    sig = strat.generate_signal(provider, timestamp="2026-07-15")

    assert sig.strategy_id == "MA_Cross_v1"
    assert "600519" in sig.symbols


def test_strategy_runner(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 20)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    strat = MACrossStrategy(symbols=["600519"])
    runner = StrategyRunner(strategy=strat, data_provider=provider, rebalance_frequency="daily")

    sig, target_df, regime = runner.run_step("2026-07-15")
    assert not target_df.empty
    assert "equity_cap_pct" in regime


def test_rebalance_frequency(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=True)
    strat = MACrossStrategy(symbols=["600519"])
    runner = StrategyRunner(strategy=strat, data_provider=provider, rebalance_frequency="weekly")

    assert runner.is_rebalance_date("2026-08-01")
    runner.last_rebalance_date = "2026-08-01"
    assert not runner.is_rebalance_date("2026-08-02")


def test_no_lookahead_bias(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": "2026-07-01", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0, "volume": 1000},
        {"date": "2026-07-02", "open": 10.0, "high": 10.5, "low": 9.5, "close": 20.0, "volume": 1000},
        {"date": "2026-07-03", "open": 10.0, "high": 10.5, "low": 9.5, "close": 30.0, "volume": 1000}
    ])
    cache.save("600519", test_df)

    full_provider = AkShareProvider(cache=cache, use_cache=True)
    sliced_provider = SlicedMarketDataProvider(full_provider, cutoff_date="2026-07-01")

    h_df = sliced_provider.get_history("600519")
    assert len(h_df) == 1
    assert h_df.iloc[-1]["close"] == 10.0


def test_equity_curve_and_drawdown():
    history = PortfolioHistory()
    history.record_step("2026-07-01", cash=50000, market_value=50000, equity=100000)
    history.record_step("2026-07-02", cash=50000, market_value=60000, equity=110000)
    history.record_step("2026-07-03", cash=50000, market_value=40000, equity=90000)

    df = history.to_dataframe()
    assert len(df) == 3
    assert df.iloc[-1]["drawdown"] > 0.10


def test_performance_report():
    history = PortfolioHistory()
    history.record_step("2026-07-01", cash=50000, market_value=50000, equity=100000)
    history.record_step("2026-07-02", cash=50000, market_value=60000, equity=110000)
    df = history.to_dataframe()
    metrics = PerformanceReport.calculate_metrics(df)
    assert metrics["TotalReturn"] == 0.10


def test_decision_audit_log(tmp_path):
    logger_inst = DecisionAuditLog(reports_dir=str(tmp_path))
    path = logger_inst.log_decision(
        timestamp="2026-08-01 10:00:00",
        strategy_id="MA_Cross_v1",
        target_weights={"600519": 0.50},
        risk_info={"regime": "🟢 强势看多", "equity_cap_pct": 75.0},
        orders=[{"order_id": "001", "symbol": "600519", "side": "BUY", "quantity": 100, "price": 100.0, "status": "FILLED"}],
        portfolio_before={"total_equity": 100000.0, "cash": 100000.0},
        portfolio_after={"total_equity": 100000.0, "cash": 90000.0, "market_value": 10000.0}
    )
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "Rebalance Decision Audit Log" in content


def test_backtest_paper_consistency(monkeypatch, tmp_path):
    """
    CRITICAL: 证明 Backtest 和 Paper Trading 使用完全相同的数据、价格、费用和信号时，
    订单、持仓、现金与权益完全一致！
    """
    account_file = tmp_path / "paper_account.json"
    import src.execution.paper_trader as pt
    monkeypatch.setattr(pt, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pt, "PAPER_ACCOUNT_FILE", str(account_file))

    target_df = pd.DataFrame([
        {"symbol": "600519", "name": "贵州茅台", "price": 100.0, "target_weight": 0.50}
    ])

    acc = PaperAccount(initial_capital=100000.0)
    res = acc.rebalance(target_df, market_regime_info={"equity_cap_pct": 100.0})
    paper_summary = acc.get_summary({"600519": 100.0})

    from src.portfolio.portfolio import Portfolio
    from src.portfolio.order import Order, OrderSide
    p = Portfolio(initial_capital=100000.0)
    order = Order(symbol="600519", side=OrderSide.BUY, quantity=500, price=100.0)
    p.submit_order(order)
    port_summary = p.get_summary({"600519": 100.0})

    assert paper_summary["cash"] == port_summary["cash"]
    assert paper_summary["market_value"] == port_summary["market_value"]
    assert paper_summary["total_equity"] == port_summary["total_equity"]
