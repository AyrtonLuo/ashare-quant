"""
test_quant.py
单元测试：验证数据计算与防未来函数逻辑
"""

import os
import sys
import pandas as pd
import numpy as np

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy.ma_cross import generate_ma_cross_signals
from src.backtest import run_vectorized_backtest

def test_ma_cross_and_shift():
    # 模拟 15 天的价格序列
    dates = pd.date_range(start="2024-01-01", periods=15, freq="D")
    # 前 5 天平坦，中间上涨，后面下跌
    prices = [10, 10, 10, 10, 10, 12, 14, 16, 18, 20, 18, 16, 14, 12, 10]
    
    df = pd.DataFrame({"date": dates, "close": prices})
    
    result_df, metrics = run_vectorized_backtest(df)
    
    # 验证关键列存在
    assert "ma_5" in result_df.columns
    assert "ma_10" in result_df.columns
    assert "signal" in result_df.columns
    assert "position" in result_df.columns
    
    # 验证 position 确实由 signal 延后一天 (shift(1)) 得到
    np.testing.assert_array_equal(
        result_df['position'].iloc[1:].values,
        result_df['signal'].iloc[:-1].values
    )
    
    # 第一天的持仓位置必须为 0
    assert result_df['position'].iloc[0] == 0.0
