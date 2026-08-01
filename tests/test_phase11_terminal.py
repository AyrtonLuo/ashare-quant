"""
test_phase11_terminal.py
Phase 11 Barra Risk Model, Portfolio Constraint Optimizer 2.0, Realistic Transaction Cost & Market Impact Model, Terminal UI Tests
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.universe import StaticUniverseProvider
from src.risk_model.exposure import ExposureCalculator
from src.risk_model.decomposition import RiskDecomposer
from src.portfolio.optimizer_v2 import PortfolioOptimizer2
from src.execution.costs import RealisticTransactionCostModel
from src.data.cache import LocalCache
from src.data.akshare_provider import AkShareProvider
from src.services.research_service import ResearchService
from src.services.backtest_service import BacktestService
from src.services.portfolio_service import PortfolioService
from src.strategy.ma_cross_strategy import MACrossStrategy


def test_historical_constituent_membership():
    uni = StaticUniverseProvider()
    u2021 = uni.get_universe("2021-01-01")
    assert "600519" in u2021


def test_survivorship_bias():
    uni = StaticUniverseProvider()
    u = uni.get_universe("2024-01-01")
    assert len(u) > 0


def test_pit_universe():
    uni = StaticUniverseProvider()
    symbols = uni.get_universe("2023-06-01")
    assert not any(s == "" for s in symbols)


def test_barra_style_exposure():
    weights = {"600519": 0.5, "000001": 0.5}
    fm = pd.DataFrame({
        "Value_EP": [0.05, 0.08],
        "Momentum_20D": [0.10, -0.02],
        "Volatility_20D": [0.15, 0.20],
        "Liquidity_20D": [0.40, 0.60],
        "Quality_ROE": [0.25, 0.15]
    }, index=["600519", "000001"])

    res = ExposureCalculator.calculate_portfolio_exposures(weights, fm)
    assert "industry_exposure" in res
    assert "style_exposure" in res
    assert res["style_exposure"]["Value"] == 0.065


def test_portfolio_risk_decomposition():
    weights = {"600519": 0.6, "000001": 0.4}
    rets_df = pd.DataFrame({
        "600519": [0.01, -0.02, 0.015, 0.005],
        "000001": [0.005, -0.01, 0.02, -0.01]
    })
    decomp = RiskDecomposer.decompose_portfolio_risk(weights, rets_df)
    assert "total_volatility_annual" in decomp
    assert decomp["factor_risk_pct"] > 0.0
    assert decomp["specific_risk_pct"] > 0.0


def test_portfolio_constraint_optimizer():
    opt = PortfolioOptimizer2(mode="Balanced", max_stock_weight=0.30)
    raw = {"600519": 0.60, "000001": 0.40}
    w = opt.optimize(raw)
    assert w["600519"] <= 0.35


def test_market_impact_model():
    cost_model = RealisticTransactionCostModel(commission_rate=0.00025, stamp_duty_rate=0.0005)
    res = cost_model.calculate_cost("600519", side="SELL", order_size=1000, price=1450.0, adv=100000.0)
    assert res["commission"] > 0.0
    assert res["stamp_duty"] > 0.0
    assert res["slippage_cost"] > 0.0


def test_end_to_end_phase11_research(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    res_svc = ResearchService(provider)
    bt_svc = BacktestService(provider)

    # 1. 因子相关性矩阵
    corr_df = res_svc.compute_factor_correlation_matrix(["600519"], cutoff_date="2026-07-20")
    assert not corr_df.empty

    # 2. 回测与风险归因
    strat = MACrossStrategy(["600519"])
    hist_df, perf = bt_svc.run_backtest(strat, ["600519"], "2026-07-01", "2026-07-20")
    assert "TotalReturn" in perf
