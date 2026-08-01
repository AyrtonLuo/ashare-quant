"""
test_phase12_productization.py
Phase 12 Productization, Research vs Demo Isolation, Stock Research Pipeline, Strategy Robustness & Reproducibility Unit Tests
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.demo_provider import DemoMarketDataProvider
from src.data.akshare_provider import AkShareProvider
from src.data.cache import LocalCache
from src.services.research_service import ResearchService
from src.strategy.robustness import StrategyRobustnessChecker
from src.strategy.ma_cross_strategy import MACrossStrategy
from src.execution.costs import RealisticTransactionCostModel


def test_research_vs_demo_isolation():
    demo = DemoMarketDataProvider()
    demo_quote = demo.get_latest("000001")
    assert demo_quote.close == 3280.50

    cache = LocalCache()
    ak = AkShareProvider(cache=cache)
    assert ak is not None


def test_stock_research_pipeline(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=True)
    res_svc = ResearchService(provider)

    pipe = res_svc.get_stock_full_research_pipeline("600519")
    assert pipe["symbol"] == "600519"
    assert "valuation" in pipe
    assert "factors" in pipe


def test_strategy_robustness_check(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    rep = StrategyRobustnessChecker.run_robustness_check(MACrossStrategy, ["600519"], provider, "2026-07-01", "2026-07-20")

    assert rep.robustness_score >= 0.0
    assert len(rep.parameter_grid_results) == 3


def test_ml_overfitting_detector():
    from src.ai.diagnostics import DiagnosticsEngine
    res = DiagnosticsEngine.detect_overfitting(train_sharpe=2.5, val_sharpe=1.8, test_sharpe=0.7)
    assert res.level == "CRITICAL"


def test_reproducibility_card(tmp_path):
    from src.runs.run_manager import RunManager
    rm = RunManager(runs_dir=str(tmp_path))
    rec = rm.start_run("r_rep_01", "Research Run")
    rm.complete_run(rec, status="SUCCESS")

    runs = rm.list_runs()
    assert runs[0]["git_commit"] is not None


def test_invalid_symbol_graceful_handling():
    p = DemoMarketDataProvider()
    m = p.get_latest("INVALID_999")
    assert m.close == 100.0


def test_market_impact_cost_calculation():
    cost_model = RealisticTransactionCostModel()
    res = cost_model.calculate_cost("600519", "BUY", order_size=5000, price=1450.0, adv=50000.0)
    assert res["total_cost"] > 0.0
