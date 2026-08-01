"""
test_phase7_services.py
Phase 7 Service Layer 与产品架构单元测试
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.cache import LocalCache
from src.data.akshare_provider import AkShareProvider
from src.execution.paper_trader import PaperAccount
from src.services.research_service import ResearchService
from src.services.backtest_service import BacktestService
from src.services.portfolio_service import PortfolioService
from src.services.ml_service import MLService
from src.services.ai_service import AIService
from src.experiments.registry import ExperimentRegistry, ExperimentRecord


def test_dashboard_data_loading(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=True)
    assert provider is not None


def test_research_service(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=True)
    svc = ResearchService(provider)

    strat = svc.create_multi_factor_strategy(symbols=["600519"])
    assert strat.strategy_id == "MultiFactor_Alpha_v2"


def test_backtest_service(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    svc = BacktestService(provider)

    from src.strategy.ma_cross_strategy import MACrossStrategy
    strat = MACrossStrategy(["600519"])
    hist_df, perf = svc.run_backtest(strat, ["600519"], "2026-07-01", "2026-07-20")

    assert not hist_df.empty
    assert "TotalReturn" in perf


def test_portfolio_service(monkeypatch, tmp_path):
    account_file = tmp_path / "paper_account.json"
    import src.execution.paper_trader as pt
    monkeypatch.setattr(pt, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pt, "PAPER_ACCOUNT_FILE", str(account_file))

    acc = PaperAccount(initial_capital=1000000.0)
    svc = PortfolioService(acc)
    summary = svc.get_portfolio_summary({"600519": 100.0})

    assert summary["cash"] == 1000000.0


def test_ml_service(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    svc = MLService(provider)
    model, X = svc.train_ml_model(["600519"], cutoff_date="2026-07-20", model_type="Linear Ridge")

    assert model.is_fitted
    strat = svc.create_ml_strategy(["600519"], model)
    assert strat.strategy_id == "ML_Alpha_Linear_Ridge"


def test_ai_service(tmp_path):
    svc = AIService()
    diag = svc.diagnose({"Sharpe": 1.5, "MaxDrawdown": 0.10})
    assert diag["level"] == "LOW"


def test_cached_market_data(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": "2026-07-01", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0, "volume": 1000}
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    h_df = provider.get_history("600519")
    assert len(h_df) == 1


def test_experiment_comparison(tmp_path):
    registry = ExperimentRegistry(exp_dir=str(tmp_path))
    rec1 = ExperimentRecord(
        experiment_id="exp_001", timestamp="2026-08-01", strategy_id="Strat_1",
        factor_config={}, parameters={}, universe=["600519"], date_range="2023-2026",
        benchmark="000300", performance_metrics={"Sharpe": 1.2}
    )
    rec2 = ExperimentRecord(
        experiment_id="exp_002", timestamp="2026-08-01", strategy_id="Strat_2",
        factor_config={}, parameters={}, universe=["600519"], date_range="2023-2026",
        benchmark="000300", performance_metrics={"Sharpe": 1.5}
    )
    registry.register_experiment(rec1)
    registry.register_experiment(rec2)

    exps = registry.list_experiments()
    assert len(exps) == 2
