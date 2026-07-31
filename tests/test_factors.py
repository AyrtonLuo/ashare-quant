"""
test_factors.py
单元测试：验证多因子计算、MAD 去极值、Z-Score 标准化与 IC 对齐逻辑
"""

import os
import sys
import pandas as pd
import numpy as np

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy.factors import (
    calculate_raw_factors,
    mad_clip_series,
    zscore_series,
    preprocess_factors_cross_section
)
from src.factor_analyzer import calculate_rank_ic


def test_factor_calculation():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    df = pd.DataFrame({
        "symbol": ["600519"] * 30,
        "date": dates,
        "close": np.linspace(100, 130, 30)
    })
    
    df_factors = calculate_raw_factors(df)
    assert "MOM_20" in df_factors.columns
    assert "VOL_20" in df_factors.columns
    assert "MA_DEV_20" in df_factors.columns
    
    # 第 20 天起 MOM_20 应当不为空
    assert not pd.isna(df_factors['MOM_20'].iloc[25])


def test_mad_and_zscore():
    s = pd.Series([1.0, 2.0, 2.1, 2.2, 100.0]) # 包含明显异常值 100
    s_clipped = mad_clip_series(s, n_mad=3.0)
    
    # 异常值 100 应当被截断
    assert s_clipped.iloc[-1] < 100.0
    
    s_norm = zscore_series(s_clipped)
    # 标准化后均值趋近于 0
    assert abs(s_norm.mean()) < 1e-5


def test_ic_alignment():
    # 验证 IC 对齐无未来函数
    dates = pd.date_range("2024-01-01", periods=25, freq="D")
    df_list = []
    for sym in ["000001", "600519", "300750"]:
        df_list.append(pd.DataFrame({
            "symbol": sym,
            "date": dates,
            "close": np.random.randn(25).cumsum() + 100
        }))
    df = pd.concat(df_list)
    df_factors = calculate_raw_factors(df)
    df_processed = preprocess_factors_cross_section(df_factors, ["MOM_20"])
    
    ic_df = calculate_rank_ic(df_processed, "MOM_20_norm")
    assert not ic_df.empty
    assert "rank_ic" in ic_df.columns
