"""
test_global_and_adaptive.py
测试全球跨市场指标抓取、自适应动态因子加权与带趋势确认的组合风控
"""

import pytest
import pandas as pd
import numpy as np
from src.data.global_market_fetcher import fetch_global_intermarket_indicators
from src.strategy.factor_engine import build_adaptive_alpha_factor
from src.risk_manager import apply_risk_managed_backtest


def test_global_market_fetcher():
    """测试全球隔夜宏观指标抓取与 5s 容错机制"""
    indicators = fetch_global_intermarket_indicators(timeout_sec=5)
    assert isinstance(indicators, dict)
    assert "A50_ret" in indicators
    assert "SPX_ret" in indicators
    assert "macro_score" in indicators
    assert "regime" in indicators
    assert -1.0 <= indicators["macro_score"] <= 1.0


def test_build_adaptive_alpha_factor():
    """测试牛熊异构状态下自适应因子的动态调权机制"""
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    records = []
    for d in dates:
        for i in range(10):
            records.append({
                "date": d,
                "symbol": f"{i:06d}",
                "close": 10.0 + (1.0 if d.day % 2 == 0 else -0.5),
                "MOM_20_norm": float(i * 0.1),
                "LOW_VOL_20_norm": float((10 - i) * 0.1),
                "MA_DEV_20_norm": 0.5
            })
    df = pd.DataFrame(records)
    
    res_df = build_adaptive_alpha_factor(df, macro_sentiment=0.5)
    assert "COMPOSITE_ALPHA_adaptive_raw" in res_df.columns
    assert "market_regime" in res_df.columns
    assert "target_position_cap" in res_df.columns


def test_trend_confirmed_risk_manager():
    """测试带大盘趋势确认的风控强平机制"""
    df = pd.DataFrame([
        {"date": "2026-01-01", "top_return": 0.01, "is_bull_trend": True},
        {"date": "2026-01-02", "top_return": -0.10, "is_bull_trend": True}, # 回撤 10%
        {"date": "2026-01-03", "top_return": -0.08, "is_bull_trend": False},# 大盘破位 + 破 15% MaxDD
        {"date": "2026-01-04", "top_return": 0.05, "is_bull_trend": False}
    ])
    
    managed_df, metrics = apply_risk_managed_backtest(df, max_dd_limit=0.15, cooldown_days=3)
    assert "风控后总收益率" in metrics
    assert "风控后最大回撤" in metrics
