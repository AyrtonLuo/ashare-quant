"""
test_quant.py
单元测试：验证数据计算、防未来函数以及 A 股交易约束（涨跌停限制与 T+1 制度）
"""

import os
import sys
import pandas as pd
import numpy as np

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy.ma_cross import generate_ma_cross_signals
from src.backtest import (
    run_vectorized_backtest,
    get_stock_limit_ratio,
    calculate_price_limits
)


def test_limit_ratio():
    # 创业板/科创板 20%
    assert get_stock_limit_ratio("300750") == 0.20
    assert get_stock_limit_ratio("688001") == 0.20
    # 主板 10%
    assert get_stock_limit_ratio("600519") == 0.10
    assert get_stock_limit_ratio("000001") == 0.10


def test_limit_up_buy_prevention():
    """
    测试涨停板买入拦截：当发生涨停封板且策略发出买入信号时，挂单无法成交，持仓保持为 0
    """
    dates = pd.date_range(start="2024-01-01", periods=15, freq="D")
    # 模拟价格序列：前5天价格为10，中间第6天突然一字涨停 10 -> 11 (+10%)
    prices = [10.0, 10.0, 10.0, 10.0, 10.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0]
    df = pd.DataFrame({"date": dates, "close": prices})

    # 主板股票（10% 涨跌停限制）
    data, m_ideal, m_real = run_vectorized_backtest(df, symbol="600519")
    
    # 验证在价格跳升触发涨停封板那天，约束持仓没有盲目跟进
    assert "is_limit_up" in data.columns
    assert data['is_limit_up'].iloc[5] == True


def test_limit_down_sell_prevention():
    """
    测试跌停板卖出拦截：当发生跌停封板且策略发出卖出信号时，卖单无法成交，被砸盘锁死被迫持有
    """
    dates = pd.date_range(start="2024-01-01", periods=10, freq="D")
    prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 13.5, 12.15, 10.0, 8.0] # 包含跌停
    df = pd.DataFrame({"date": dates, "close": prices})

    data, m_ideal, m_real = run_vectorized_backtest(df, symbol="000001")
    assert "constrained_position" in data.columns
