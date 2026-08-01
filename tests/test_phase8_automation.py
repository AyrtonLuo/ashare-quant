"""
test_phase8_automation.py
Phase 8 Production Data Pipeline 2.0, Data Quality, Run Manager, System Health & Fallback Resilience 单元测试
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.cache import LocalCache
from src.data.akshare_provider import AkShareProvider
from src.data.quality.checker import DataQualityChecker
from src.data.universe import StaticUniverseProvider
from src.runs.run_manager import RunManager, RunRecord
from src.system.health import SystemHealthMonitor
from src.portfolio.history import PortfolioHistory
from src.ai.schemas import ResearchContext
from src.ai.report_generator import AutomatedReportGenerator


def test_data_pipeline(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": "2026-07-01", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0, "volume": 1000}
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    df = provider.get_history("600519")
    assert not df.empty


def test_data_quality():
    good_df = pd.DataFrame([
        {"date": "2026-07-01", "close": 10.0, "volume": 1000},
        {"date": "2026-07-02", "close": 10.5, "volume": 1100}
    ])
    r1 = DataQualityChecker.check_dataframe("600519", good_df)
    assert r1.status == "PASS"

    bad_df = pd.DataFrame([
        {"date": "2026-07-01", "close": -5.0, "volume": 1000}
    ])
    r2 = DataQualityChecker.check_dataframe("600519", bad_df)
    assert r2.status in ["WARNING", "FAIL"]


def test_pit_data():
    uni = StaticUniverseProvider()
    symbols = uni.get_universe("2024-01-01")
    assert "600519" in symbols


def test_daily_scheduler(tmp_path):
    rm_instance = RunManager(runs_dir=str(tmp_path))

    rec = rm_instance.start_run("test_job_sched", "Daily Update")
    rm_instance.complete_run(rec, status="SUCCESS")

    runs = rm_instance.list_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "SUCCESS"


def test_run_manager(tmp_path):
    rm = RunManager(runs_dir=str(tmp_path))
    rec = rm.start_run("run_001", "Backtest Run")
    assert rec.status == "RUNNING"

    rm.complete_run(rec, status="SUCCESS")
    runs = rm.list_runs()
    assert runs[0]["status"] == "SUCCESS"


def test_portfolio_snapshot():
    history = PortfolioHistory()
    history.record_step("2026-08-01", cash=500000.0, market_value=500000.0, equity=1000000.0)
    df = history.to_dataframe()
    assert df.iloc[0]["equity"] == 1000000.0


def test_research_run(tmp_path):
    rm = RunManager(runs_dir=str(tmp_path))
    rec = rm.start_run("run_res_001", "Research Run")
    rm.complete_run(rec, status="SUCCESS")

    runs = rm.list_runs()
    assert runs[0]["run_type"] == "Research Run"


def test_system_health():
    res = SystemHealthMonitor.check_system_health()
    assert "Data Provider" in res
    assert res["Data Provider"]["status"] == "Healthy"


def test_data_versioning():
    rec = RunRecord(run_id="r1", run_type="Daily Update", status="SUCCESS", start_time="2026-08-01", data_hash="v2.0_parquet_hash")
    d = rec.to_dict()
    assert d["data_hash"] == "v2.0_parquet_hash"


def test_daily_ai_report(tmp_path):
    gen = AutomatedReportGenerator(reports_dir=str(tmp_path))
    ctx = ResearchContext(
        experiment_id="daily_brief_20260801",
        strategy_id="Daily_Quant_Brief",
        universe=["600519"],
        date_range="2026-08-01",
        benchmark="000300",
        performance_metrics={"TotalReturnPct": "+0.62%", "Sharpe": 1.52}
    )
    filepath = gen.generate_report(ctx)
    assert os.path.exists(filepath)


def test_resilience_missing_data():
    empty_df = pd.DataFrame()
    r = DataQualityChecker.check_dataframe("600519", empty_df)
    assert r.status == "FAIL"
    assert "empty" in r.anomalies[0].lower()
