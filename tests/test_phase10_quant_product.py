"""
test_phase10_quant_product.py
Phase 10 End-to-End Research Pipeline, Point-in-Time Fundamental Data & Reproducibility Unit Tests
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.fundamental.provider import PITFundamentalProvider
from src.data.cache import LocalCache
from src.data.akshare_provider import AkShareProvider
from src.services.research_service import ResearchService
from src.services.backtest_service import BacktestService
from src.services.ml_service import MLService
from src.services.ai_service import AIService
from src.strategy.ma_cross_strategy import MACrossStrategy


def test_fundamental_point_in_time():
    pit = PITFundamentalProvider()
    # 2024-11-01 截面：此时 2024-09-30 季报已在 2024-10-30 披露
    f1 = pit.get_fundamental("600519", cutoff_date="2024-11-01")
    assert f1.timestamp == "2024-09-30"
    assert f1.publication_date == "2024-10-30"


def test_no_future_financial_data():
    pit = PITFundamentalProvider()
    # 2025-01-15 截面：年报 (2024-12-31) 尚未在 2025-03-30 披露，系统绝不可使用 2024 年年报数据！
    f2 = pit.get_fundamental("600519", cutoff_date="2025-01-15")
    assert f2.timestamp == "2024-09-30"
    assert f2.publication_date <= "2025-01-15"


def test_financial_publication_lag():
    pit = PITFundamentalProvider()
    # 2025-04-01 截面：此时 2024 年年报 (2025-03-30 披露) 已解锁
    f3 = pit.get_fundamental("600519", cutoff_date="2025-04-01")
    assert f3.timestamp == "2024-12-31"
    assert f3.publication_date == "2025-03-30"


def test_end_to_end_research_pipeline(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    res_svc = ResearchService(provider)
    bt_svc = BacktestService(provider)
    ml_svc = MLService(provider)
    ai_svc = AIService()

    # Step 1: 因子矩阵
    f_matrix = res_svc.run_factor_analysis(["600519"], cutoff_date="2026-07-20")
    assert not f_matrix.empty

    # Step 2: ML 模型比较
    comp_df = ml_svc.compare_ml_models(["600519"], cutoff_date="2026-07-20")
    assert len(comp_df) == 3

    # Step 3: 运行回测
    strat = MACrossStrategy(["600519"])
    hist_df, perf = bt_svc.run_backtest(strat, ["600519"], "2026-07-01", "2026-07-20")
    assert not hist_df.empty

    # Step 4: AI 智能研报导出
    report_path = ai_svc.generate_research_report("exp_e2e", "E2E_Test_Strategy", ["600519"], "2026-07", perf)
    assert os.path.exists(report_path)


def test_backtest_reproducibility(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    bt_svc = BacktestService(provider)

    strat1 = MACrossStrategy(["600519"])
    h1, p1 = bt_svc.run_backtest(strat1, ["600519"], "2026-07-01", "2026-07-20")

    strat2 = MACrossStrategy(["600519"])
    h2, p2 = bt_svc.run_backtest(strat2, ["600519"], "2026-07-01", "2026-07-20")

    assert p1["TotalReturn"] == p2["TotalReturn"]
    assert p1["Sharpe"] == p2["Sharpe"]
