"""
test_portfolio_optimizer.py
测试个人资金容量计算器、一手 (100股) 约束过滤与高价股顺延剔除
"""

import pytest
import pandas as pd
from src.strategy.portfolio_optimizer import (
    auto_calculate_portfolio_size,
    filter_and_allocate_portfolio
)


def test_auto_calculate_portfolio_size():
    """测试不同资金档位自动推荐持仓只数"""
    assert auto_calculate_portfolio_size(50000) == 5
    assert auto_calculate_portfolio_size(200000) == 8
    assert auto_calculate_portfolio_size(1000000) == 12
    assert auto_calculate_portfolio_size(5000000) == 15


def test_filter_and_allocate_portfolio():
    """测试 100 股建仓约束与高价股剔除顺延"""
    mock_df = pd.DataFrame([
        {"symbol": "600519", "name": "贵州茅台", "close": 1480.0, "COMPOSITE_ALPHA_norm": 1.5},
        {"symbol": "600941", "name": "中国移动", "close": 97.41, "COMPOSITE_ALPHA_norm": 1.2},
        {"symbol": "000001", "name": "平安银行", "close": 11.20, "COMPOSITE_ALPHA_norm": 1.1},
        {"symbol": "600028", "name": "中国石化", "close": 6.30, "COMPOSITE_ALPHA_norm": 1.0},
    ])

    res = filter_and_allocate_portfolio(mock_df, total_capital=100000.0, target_count=3)
    p_df = res['portfolio_df']

    # 贵州茅台应被剔除
    assert len(res['skipped_stocks']) == 1
    assert res['skipped_stocks'][0]['symbol'] == '600519'

    # 包含后三只股票，且拟买入股数均为 100 的整数倍
    assert len(p_df) == 3
    for shares in p_df['shares']:
        assert shares % 100 == 0
        assert shares >= 100
