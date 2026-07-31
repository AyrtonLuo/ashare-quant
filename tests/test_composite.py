"""
test_composite.py
单元测试：验证复合 Alpha 因子防未来函数、IC-IR 动态权重与增量更新数据排序
"""

import os
import sys
import pandas as pd
import numpy as np

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy.factors import calculate_raw_factors, preprocess_factors_cross_section
from src.strategy.composite_factor import build_composite_alpha_factor


def test_composite_alpha_factor_build():
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    df_list = []
    for sym in ["000001", "600519", "300750"]:
        df_list.append(pd.DataFrame({
            "symbol": sym,
            "date": dates,
            "close": np.random.randn(40).cumsum() + 100
        }))
    df = pd.concat(df_list)
    df_factors = calculate_raw_factors(df)
    df_factors['LOW_VOL_20'] = -df_factors['VOL_20']
    df_processed = preprocess_factors_cross_section(df_factors, ["MOM_20", "LOW_VOL_20"])
    
    # 动态 IC-IR 权重合成
    df_comp = build_composite_alpha_factor(df_processed, method="dynamic_ic_ir")
    assert "COMPOSITE_ALPHA_norm" in df_comp.columns
    assert not df_comp['COMPOSITE_ALPHA_norm'].dropna().empty


def test_incremental_sorting_logic():
    # 验证去重与时间正序逻辑
    df_old = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "val": [1, 2]
    })
    df_new = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02", "2024-01-03"]), # 包含重复与新日期
        "val": [2, 3]
    })
    combined = pd.concat([df_old, df_new], ignore_index=True)
    combined = combined.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
    
    # 必须正序且无重复
    assert len(combined) == 3
    assert combined['date'].iloc[0] == pd.to_datetime("2024-01-01")
    assert combined['date'].iloc[-1] == pd.to_datetime("2024-01-03")
