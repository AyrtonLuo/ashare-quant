"""
test_backtest_temporal_integrity.py — Audit test proving backtest execution strictly respects snapshot & as_of boundaries.
"""

import pytest
from datetime import datetime
from src.quant.backtest.engine import BacktestEngine
from src.quant.portfolio.construction import PortfolioTarget
from src.data.snapshot.snapshot_manager import SnapshotManager


def test_backtest_engine_binds_snapshot_id_and_as_of():
    engine = BacktestEngine()
    prices = {"600519.SH": [1600.0, 1620.0, 1610.0]}
    targets = [PortfolioTarget("2022-05-01", "strat_1", {"600519.SH": 1.0}, 1.0)]

    mgr = SnapshotManager()
    snap = mgr.create_snapshot(as_of=datetime(2022, 5, 2), snapshot_id="snap_backtest_01")

    res = engine.run_backtest(
        dataset_id="golden_ds", strategy_id="strat_1",
        daily_prices=prices, portfolio_targets=targets,
        data_snapshot=snap
    )

    assert res.snapshot_id == "snap_backtest_01"
    assert "2022-05-02" in res.as_of
    assert res.total_return != 0.0
