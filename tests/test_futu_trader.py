"""
test_futu_trader.py
测试富途 OpenD 港股模拟交易引擎 (TrdMarket.HK)：
1. 校验 A 股/港股代码至富途港股格式转义 (HK.00941, HK.00700)
2. 校验 100 股最小交易单位整倍数取整逻辑
3. 校验 HK 港股模拟盘 Mock 调仓逻辑
"""

import pytest
import pandas as pd
from src.execution.futu_trader import to_futu_hk_code, to_ashare_symbol, FutuSimTrader


def test_futu_hk_code_conversion():
    """测试 A 股/港股代码至富途港股代码映射"""
    assert to_futu_hk_code("600941") == "HK.00941"  # 中国移动 AH 映射
    assert to_futu_hk_code("601398") == "HK.01398"  # 工商银行 AH 映射
    assert to_futu_hk_code("00700") == "HK.00700"    # 腾讯控股
    assert to_futu_hk_code("09988") == "HK.09988"    # 阿里巴巴

    assert to_ashare_symbol("HK.00941") == "00941"
    assert to_ashare_symbol("HK.00700") == "00700"


def test_futu_hk_rebalance_lot_size_constraint():
    """测试富途港股模拟盘调仓与 100 股一手整倍数限制"""
    sample_df = pd.DataFrame([
        {"symbol": "600941", "name": "中国移动", "close": 97.41},
        {"symbol": "00700", "name": "腾讯控股", "close": 380.00},
        {"symbol": "09988", "name": "阿里巴巴", "close": 85.20}
    ])

    # 1. 测试新空账户调仓 (0 笔卖单)
    trader = FutuSimTrader(is_mock=True)
    res_empty = trader.execute_rebalance(sample_df, initial_mock_cash=1000000.0)
    assert "HK Market" in res_empty["mode"]
    assert len(res_empty["sell_orders"]) == 0
    assert len(res_empty["buy_orders"]) == 3

    # 2. 测试带旧持仓的模拟盘调仓 (平仓不在 Top39 名单内的旧港股)
    mock_pos = {"HK.00005": {"qty": 2000, "price": 60.50, "name": "汇丰控股"}}
    res_with_pos = trader.execute_rebalance(sample_df, initial_mock_cash=1000000.0, mock_positions=mock_pos)

    assert "sell_orders" in res_with_pos
    assert "buy_orders" in res_with_pos

    # 校验买单股数必须是 100 股整倍数
    for b_order in res_with_pos["buy_orders"]:
        qty = b_order["buy_qty"]
        assert qty >= 100
        assert qty % 100 == 0
        assert b_order["futu_code"].startswith("HK.")

    # 校验卖单平仓旧持仓
    assert len(res_with_pos["sell_orders"]) == 1
    assert res_with_pos["sell_orders"][0]["symbol"] == "00005"
