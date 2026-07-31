"""
test_futu_trader.py
测试富途 OpenD 模拟交易引擎：
1. 校验 A 股代码与富途格式转义 (SH/SZ)
2. 校验 100 股最小交易单位整倍数取整逻辑
3. 校验 Mock 调仓逻辑、卖单平仓与买单生成
"""

import pytest
import pandas as pd
from src.execution.futu_trader import to_futu_code, to_ashare_symbol, FutuSimTrader


def test_futu_code_conversion():
    """测试 A 股代码与富途代码互转"""
    assert to_futu_code("600941") == "SH.600941"
    assert to_futu_code("688578") == "SH.688578"
    assert to_futu_code("000001") == "SZ.000001"
    assert to_futu_code("300750") == "SZ.300750"

    assert to_ashare_symbol("SH.600941") == "600941"
    assert to_ashare_symbol("SZ.000001") == "000001"


def test_futu_rebalance_lot_size_constraint():
    """测试富途模拟盘调仓与 100 股一手整倍数限制"""
    sample_df = pd.DataFrame([
        {"symbol": "600941", "name": "中国移动", "close": 97.41},
        {"symbol": "000651", "name": "格力电器", "close": 42.30},
        {"symbol": "000001", "name": "平安银行", "close": 11.63}
    ])

    trader = FutuSimTrader(is_mock=True)
    res = trader.execute_rebalance(sample_df, initial_mock_cash=1000000.0)

    assert "mode" in res
    assert "sell_orders" in res
    assert "buy_orders" in res
    assert "account_summary" in res

    # 校验所有买单交易股数必须是 100 股的整数倍且 >= 100
    for b_order in res["buy_orders"]:
        qty = b_order["buy_qty"]
        assert qty >= 100
        assert qty % 100 == 0
        assert b_order["symbol"] in ["600941", "000651", "000001"]

    # 校验卖单中清除了不在名单中的旧股票
    assert len(res["sell_orders"]) >= 1
    assert res["sell_orders"][0]["symbol"] == "600000"
