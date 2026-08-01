"""
backtest_vbt.py
基于 VectorBT 开源框架实现的向量化回测引擎
与现版 pandas 手写回测引擎 (src/backtest.py) 进行逻辑对齐与结果验证
"""

import os
import sys
import pandas as pd
import numpy as np
import vectorbt as vbt
from typing import Dict, Any, Tuple

# 关联项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.strategy.ma_cross import generate_ma_cross_signals

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def run_vectorbt_backtest(df: pd.DataFrame, symbol: str = "600519", initial_capital: float = 100000.0) -> Tuple[vbt.Portfolio, Dict[str, Any]]:
    """
    使用 VectorBT (vbt.Portfolio.from_signals) 运行双均线策略回测

    参数:
        df: 股票历史日线 DataFrame (包含 'date', 'close' 列)
        symbol: 股票代码
        initial_capital: 初始资金 (默认 100000.0)

    返回:
        (portfolio, metrics_dict)
    """
    # 1. 生成 MA5/MA10 双均线策略信号
    data = generate_ma_cross_signals(df)

    # 2. 提取买入 (entries) 与卖出 (exits) 信号状态
    entries = (data['signal'] == 1.0) & (data['signal'].shift(1) != 1.0)
    exits = (data['signal'] == 0.0) & (data['signal'].shift(1) == 1.0)

    # 3. 构建 VectorBT Portfolio 组合
    pf = vbt.Portfolio.from_signals(
        close=data['close'],
        entries=entries,
        exits=exits,
        freq='1D',
        init_cash=initial_capital,
        fees=0.0,
        slippage=0.0
    )

    # 4. 计算绩效指标 (对齐总收益率、最大回撤、夏普比率)
    total_return = float(pf.total_return())
    max_drawdown = abs(float(pf.max_drawdown()))

    # 计算日度标准夏普比率 (risk_free=0.0)
    returns = pf.returns()
    if returns.std() > 0:
        sharpe_ratio = float((returns.mean() / returns.std()) * np.sqrt(252))
    else:
        sharpe_ratio = 0.0

    metrics = {
        "代码": symbol,
        "初始资金": initial_capital,
        "最终资产": float(pf.final_value()),
        "总收益率": total_return,
        "最大回撤": max_drawdown,
        "夏普比率": sharpe_ratio,
        "vbt_annualized_sharpe": float(pf.sharpe_ratio(risk_free=0.0))
    }

    return pf, metrics


def print_vbt_report(symbol: str, name: str, metrics: Dict[str, Any]):
    """
    打印 VectorBT 回测绩效报告
    """
    print("\n" + "="*70)
    print(f" 🚀 VectorBT (vbt.Portfolio.from_signals) 回测报告: {name} ({symbol})")
    print("="*70)
    print(f"  • 总收益率 (Total Return)   : {metrics['总收益率']*100:.2f}%")
    print(f"  • 最大回撤 (Max Drawdown)   : {metrics['最大回撤']*100:.2f}%")
    print(f"  • 策略夏普比率 (Sharpe Ratio): {metrics['夏普比率']:.2f}")
    print(f"  • 最终组合资产 (Final Value) : ¥{metrics['最终资产']:,.2f}")
    print("="*70)


if __name__ == "__main__":
    parquet_file = os.path.join(DATA_DIR, "600519.parquet")
    if os.path.exists(parquet_file):
        df_600519 = pd.read_parquet(parquet_file)
        pf, metrics = run_vectorbt_backtest(df_600519, symbol="600519")
        print_vbt_report("600519", "贵州茅台", metrics)
    else:
        print("未找到 600519.parquet 数据文件，请检查 data 目录。")
