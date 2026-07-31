"""
test_risk_and_decay.py
单元测试：验证组合风控熔断器状态机与 Alpha 衰减诊断告警逻辑
"""

import os
import sys
import pandas as pd
import numpy as np

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.risk_manager import apply_risk_managed_backtest
from src.strategy_decay_analyzer import diagnose_alpha_decay


def test_circuit_breaker_state_machine():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    
    # 构造极端的暴跌收益率序列：前2天上涨，第3天大跌 -20% 触发 15% 熔断
    returns = [0.05, 0.05, -0.20] + [0.01] * 27
    
    res_df = pd.DataFrame({
        "date": dates,
        "top_return": returns,
        "cum_top": (1 + pd.Series(returns)).cumprod()
    })
    
    managed_df, metrics = apply_risk_managed_backtest(res_df, max_dd_limit=0.15, cooldown_days=10)
    
    # 验证触发了熔断
    assert metrics["熔断触发次数"] >= 1
    # 验证处于熔断冷静期时，收益率为 0
    broken_rows = managed_df[managed_df['in_circuit_breaker']]
    assert not broken_rows.empty
    assert (broken_rows['managed_return'] == 0.0).all()


def test_alpha_decay_diagnostic():
    dates = pd.date_range("2024-01-01", periods=70, freq="D")
    # 构造衰减的 IC 序列 (后面全是负 IC)
    ic_values = [0.1] * 30 + [-0.1] * 40
    
    ic_df = pd.DataFrame({
        "date": dates,
        "rank_ic": ic_values
    })
    
    diag = diagnose_alpha_decay(ic_df, "TEST_FACTOR", rolling_window=60)
    assert "is_decayed" in diag
    assert diag["is_decayed"] == True
    assert "DECAY_WARNING" in diag["status"]
