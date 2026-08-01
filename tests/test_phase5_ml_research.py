"""
test_phase5_ml_research.py
Phase 5 全套 ML Feature Engineering, ML Models, TimeSeries Split, MLAlphaStrategy 与 Reproducibility 单元测试
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.cache import LocalCache
from src.data.akshare_provider import AkShareProvider
from src.ml.features import FeatureExtractor
from src.ml.dataset import MLDatasetBuilder
from src.ml.split import TimeSeriesSplitter, WalkForwardSplitter
from src.ml.models.linear import LinearModel
from src.ml.models.tree import RandomForestModel, GradientBoostingModel
from src.ml.evaluation import MLEvaluator
from src.strategy.ml_alpha_strategy import MLAlphaStrategy
from src.backtest_engine_v2 import BacktestEngine2, SlicedMarketDataProvider
from src.experiments.registry import ExperimentRegistry, ExperimentRecord


def test_feature_dataset(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)
    provider = AkShareProvider(cache=cache, use_cache=True)

    extractor = FeatureExtractor(provider)
    f_matrix = extractor.extract_features_on_date(["600519"], cutoff_date="2026-07-20")
    assert not f_matrix.empty
    assert "Momentum_20D" in f_matrix.columns


def test_feature_target_alignment(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)
    provider = AkShareProvider(cache=cache, use_cache=True)

    builder = MLDatasetBuilder(provider, forward_days=2)
    df_x, df_y = builder.build_dataset(["600519"], ["2026-07-05"])
    assert not df_x.empty
    assert not df_y.empty


def test_time_series_split():
    idx = pd.MultiIndex.from_tuples([
        ("2022-01-01", "600519"),
        ("2023-05-01", "600519"),
        ("2024-06-01", "600519"),
        ("2025-08-01", "600519")
    ], names=["date", "symbol"])

    df_x = pd.DataFrame({"feat": [1, 2, 3, 4]}, index=idx)
    df_y = pd.Series([0.1, 0.2, 0.3, 0.4], index=idx)

    (x_tr, y_tr), (x_va, y_va), (x_te, y_te) = TimeSeriesSplitter.train_val_test_split(df_x, df_y, train_end="2023-12-31", val_end="2024-12-31")

    assert len(x_tr) == 2
    assert len(x_va) == 1
    assert len(x_te) == 1


def test_ml_no_future_features(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": "2026-07-01", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0, "volume": 1000},
        {"date": "2026-07-02", "open": 10.0, "high": 10.5, "low": 9.5, "close": 100.0, "volume": 1000}
    ])
    cache.save("600519", test_df)

    full_provider = AkShareProvider(cache=cache, use_cache=True)
    sliced_provider = SlicedMarketDataProvider(full_provider, cutoff_date="2026-07-01")

    extractor = FeatureExtractor(sliced_provider)
    f_matrix = extractor.extract_features_on_date(["600519"], cutoff_date="2026-07-01")

    assert f_matrix.loc["600519", "Momentum_20D"] == 0.0


def test_linear_model():
    X = pd.DataFrame({"f1": [1.0, 2.0, 3.0], "f2": [0.1, 0.2, 0.3]})
    y = pd.Series([10.0, 20.0, 30.0])

    m = LinearModel()
    m.fit(X, y)
    preds = m.predict(X)
    assert len(preds) == 3
    assert m.is_fitted


def test_tree_model():
    X = pd.DataFrame({"f1": [1.0, 2.0, 3.0, 4.0], "f2": [0.1, 0.2, 0.3, 0.4]})
    y = pd.Series([10.0, 20.0, 30.0, 40.0])

    rf = RandomForestModel(n_estimators=10)
    rf.fit(X, y)
    preds = rf.predict(X)
    assert len(preds) == 4
    imp = rf.get_feature_importance(["f1", "f2"])
    assert "f1" in imp


def test_prediction_pipeline():
    y_true = pd.Series([0.10, 0.05, -0.02, 0.08])
    y_pred = pd.Series([0.09, 0.04, -0.01, 0.07])

    metrics = MLEvaluator.evaluate(y_true, y_pred)
    assert metrics["RMSE"] < 0.05
    assert metrics["IC"] > 0.90


def test_ml_strategy(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)
    provider = AkShareProvider(cache=cache, use_cache=True)

    X = pd.DataFrame({"Momentum_20D": [1.0], "Value_EP": [0.5]}, index=["600519"])
    y = pd.Series([0.15], index=["600519"])

    model = LinearModel()
    model.fit(X, y)

    strat = MLAlphaStrategy(symbols=["600519"], model=model, top_k=1)
    sig = strat.generate_signal(provider, timestamp="2026-07-20")

    assert sig.strategy_id == "ML_Alpha_Linear_Ridge"
    assert "600519" in sig.target_weights


def test_ml_backtest(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)
    provider = AkShareProvider(cache=cache, use_cache=True)

    X = pd.DataFrame({"Momentum_20D": [1.0], "Value_EP": [0.5]}, index=["600519"])
    y = pd.Series([0.15], index=["600519"])

    model = LinearModel()
    model.fit(X, y)

    strat = MLAlphaStrategy(symbols=["600519"], model=model, top_k=1)
    engine = BacktestEngine2(strategy=strat, data_provider=provider, initial_capital=100000.0)

    history_df, perf, _ = engine.run(symbols=["600519"], start_date="2026-07-01", end_date="2026-07-20")
    assert not history_df.empty
    assert "TotalReturn" in perf


def test_ml_reproducibility(tmp_path):
    X = pd.DataFrame({"f1": [1.0, 2.0, 3.0], "f2": [0.1, 0.2, 0.3]})
    y = pd.Series([10.0, 20.0, 30.0])

    m1 = RandomForestModel(n_estimators=10, random_state=42)
    m1.fit(X, y)
    p1 = m1.predict(X)

    m2 = RandomForestModel(n_estimators=10, random_state=42)
    m2.fit(X, y)
    p2 = m2.predict(X)

    assert np.allclose(p1.values, p2.values)


def test_walk_forward_validation():
    dates = [f"{y}-05-01" for y in range(2020, 2026)]
    folds = WalkForwardSplitter.generate_folds(dates, train_window_years=3, test_window_years=1)
    assert len(folds) >= 2
    assert folds[0]["train_end"] == "2022-12-31"
    assert folds[0]["test_start"] == "2023-01-01"


def test_ml_experiment_registry(tmp_path):
    registry = ExperimentRegistry(exp_dir=str(tmp_path))
    rec = ExperimentRecord(
        experiment_id="exp_ml_001",
        timestamp="2026-08-01 10:00:00",
        strategy_id="ML_Alpha_RandomForest",
        factor_config={"Momentum": 1.0, "Value": 1.0},
        parameters={"model_type": "RandomForest", "forward_days": 20, "train_period": "2020-2023", "test_period": "2024-2026"},
        universe=["600519"],
        date_range="2020-2026",
        benchmark="000300",
        performance_metrics={"RMSE": 0.02, "IC": 0.065, "RankIC": 0.08, "ICIR": 1.25, "Sharpe": 1.45}
    )
    fpath = registry.register_experiment(rec)
    assert os.path.exists(fpath)
    exps = registry.list_experiments()
    assert exps[0]["parameters"]["model_type"] == "RandomForest"
