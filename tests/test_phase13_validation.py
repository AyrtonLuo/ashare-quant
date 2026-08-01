"""
test_phase13_validation.py
Phase 13 Real-World Validation, External Data Cross-Validation, Walk-Forward Stability, Factor Decay, Statistical Significance, Stress Testing Unit Tests
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
from src.data.validation.cross_validator import ExternalDataValidator
from src.stats.significance import StatisticalSignificanceTester
from src.risk_model.stress_test import PortfolioStressTester
from src.factors.analytics import FactorAnalytics
from src.strategy.walk_forward import WalkForwardRunner
from src.strategy.ma_cross_strategy import MACrossStrategy


def test_external_data_cross_validation():
    provider = DemoMarketDataProvider()
    rep = ExternalDataValidator.validate_data(provider)
    assert rep.passed_count > 0
    assert len(rep.audit_records) == 7
    assert rep.audit_records[0]["passed"] is True




def test_walk_forward_stability(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    wf_rep = WalkForwardRunner.run_walk_forward_validation(MACrossStrategy, ["600519"], provider)

    assert wf_rep.folds_count == 5
    assert len(wf_rep.fold_details) == 5
    assert wf_rep.mean_oos_sharpe > 0.0


def test_factor_decay_curve():
    rep = FactorAnalytics.analyze_factor_decay("Momentum_20D", pd.Series([1.0, 2.0]))
    assert "1D" in rep.decay_curve
    assert "60D" in rep.decay_curve
    assert rep.decay_curve["1D"] > rep.decay_curve["60D"]  # 展现 Alpha 半衰期指数衰减性


def test_naive_baseline_comparison():
    rets = pd.Series(np.random.normal(0.0015, 0.012, 252))
    rep = StatisticalSignificanceTester.test_sharpe_significance(rets)
    assert rep.sharpe > 0.0
    assert isinstance(rep.ml_vs_naive_superiority, bool)


def test_statistical_significance_bootstrap():
    rets = pd.Series(np.random.normal(0.002, 0.010, 252))
    rep = StatisticalSignificanceTester.test_sharpe_significance(rets, n_bootstrap=100)
    assert rep.ci_lower < rep.ci_upper
    assert rep.p_value <= 1.0


def test_portfolio_stress_test():
    st_rep = PortfolioStressTester.run_stress_test(portfolio_equity=1000000.0, beta=0.90)
    assert st_rep.base_equity == 1000000.0
    assert len(st_rep.scenarios_results) == 5
    assert "CRITICAL" in [x["risk_level"] for x in st_rep.scenarios_results]


def test_source_grounded_ai_interpreter():
    from src.ai.diagnostics import DiagnosticsEngine
    diag = DiagnosticsEngine.diagnose_performance({"Sharpe": 0.45, "MaxDrawdown": 0.35})
    assert diag.level in ["HIGH", "CRITICAL", "MODERATE", "LOW"]
