"""
test_phase4_quant_research.py
Phase 4 全套 Factor Engine、MultiFactorStrategy、Experiment Registry 与 Reproducibility 单元测试
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.cache import LocalCache
from src.data.akshare_provider import AkShareProvider
from src.factors.base import Factor
from src.factors.momentum import MomentumFactor
from src.factors.value import ValueFactor
from src.factors.quality import QualityFactor
from src.factors.volatility import VolatilityFactor
from src.factors.liquidity import LiquidityFactor
from src.factors.engine import FactorEngine, mad_winsorize, zscore_standardize
from src.strategy.multi_factor_strategy import MultiFactorStrategy
from src.experiments.registry import ExperimentRegistry, ExperimentRecord
from src.data.universe import StaticUniverseProvider


def test_factor_interface(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)
    provider = AkShareProvider(cache=cache, use_cache=True)

    mom = MomentumFactor(20)
    assert mom.name == "Momentum_20D"
    val = mom.compute("600519", provider)
    assert val > 0.0


def test_momentum_factor(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)
    provider = AkShareProvider(cache=cache, use_cache=True)

    mom = MomentumFactor(20)
    score = mom.compute("600519", provider)
    assert score > 0.0


def test_value_factor(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=True)
    vf = ValueFactor()
    val = vf.compute("600519", provider)
    assert val > 0.0


def test_factor_normalization():
    s = pd.Series([1.0, 2.0, 3.0, 100.0, -50.0])
    w = mad_winsorize(s, n_mad=3.0)
    assert w.max() < 100.0
    z = zscore_standardize(w)
    assert abs(z.mean()) < 1e-5


def test_factor_neutralization(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=True)
    engine = FactorEngine(provider)
    matrix = engine.compute_factor_matrix(
        symbols=["600519", "000001", "600690"],
        factors=[MomentumFactor(20), ValueFactor()],
        neutralize=True
    )
    assert matrix.shape == (3, 2)


def test_composite_alpha(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=True)
    engine = FactorEngine(provider)
    matrix = engine.compute_factor_matrix(
        symbols=["600519", "000001"],
        factors=[MomentumFactor(20), ValueFactor()]
    )
    alpha = engine.combine_composite_alpha(matrix, {"Momentum_20D": 0.6, "Value_EP": 0.4})
    assert len(alpha) == 2


def test_multifactor_strategy(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)
    cache.save("000001", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    strat = MultiFactorStrategy(symbols=["600519", "000001"], top_k=2)
    sig = strat.generate_signal(provider, timestamp="2026-07-20")

    assert sig.strategy_id == "MultiFactor_Alpha_v2"
    assert len(sig.target_weights) > 0


def test_factor_no_lookahead(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": "2026-07-01", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0, "volume": 1000},
        {"date": "2026-07-02", "open": 10.0, "high": 10.5, "low": 9.5, "close": 20.0, "volume": 1000},
        {"date": "2026-07-03", "open": 10.0, "high": 10.5, "low": 9.5, "close": 30.0, "volume": 1000}
    ])
    cache.save("600519", test_df)

    from src.backtest_engine_v2 import SlicedMarketDataProvider
    full_provider = AkShareProvider(cache=cache, use_cache=True)
    sliced_provider = SlicedMarketDataProvider(full_provider, cutoff_date="2026-07-01")

    mom = MomentumFactor(1)
    val = mom.compute("600519", sliced_provider)
    assert val == 0.0


def test_experiment_registry(tmp_path):
    registry = ExperimentRegistry(exp_dir=str(tmp_path))
    rec = ExperimentRecord(
        experiment_id="exp_test_001",
        timestamp="2026-08-01 10:00:00",
        strategy_id="MultiFactor_Alpha_v2",
        factor_config={"Momentum": 0.5, "Value": 0.5},
        parameters={"top_k": 3},
        universe=["600519", "000001"],
        date_range="2023-2026",
        benchmark="000300",
        performance_metrics={"TotalReturn": 0.15, "Sharpe": 1.2}
    )
    fpath = registry.register_experiment(rec)
    assert os.path.exists(fpath)

    exps = registry.list_experiments()
    assert len(exps) == 1
    assert exps[0]["experiment_id"] == "exp_test_001"


def test_factor_reproducibility(tmp_path):
    registry = ExperimentRegistry(exp_dir=str(tmp_path))
    rec1 = ExperimentRecord(
        experiment_id="exp_rep_1",
        timestamp="2026-08-01",
        strategy_id="MultiFactor",
        factor_config={"MOM": 0.5},
        parameters={}, universe=["600519"], date_range="2023-2026", benchmark="000300",
        performance_metrics={"Sharpe": 1.25}
    )
    registry.register_experiment(rec1)

    exps = registry.list_experiments()
    assert exps[0]["performance_metrics"]["Sharpe"] == 1.25


def test_strategy_lab_pipeline(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    strat = MultiFactorStrategy(symbols=["600519"], top_k=1)
    sig = strat.generate_signal(provider, timestamp="2026-07-20")

    assert sig.strategy_id == "MultiFactor_Alpha_v2"
    assert "600519" in sig.target_weights
