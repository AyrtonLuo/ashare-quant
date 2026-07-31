"""
backtest.py
向量化回测引擎核心实现
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.strategy.ma_cross import generate_ma_cross_signals

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def run_vectorized_backtest(df: pd.DataFrame, initial_capital: float = 100000.0) -> tuple[pd.DataFrame, dict]:
    """
    运行基于 Pandas 的向量化择时回测
    
    参数:
        df: 包含交易日与收盘价的 DataFrame
        initial_capital: 初始资金 (默认 10万)
        
    返回:
        (backtest_df, metrics_dict)
    """
    # 1. 生成双均线原始交易信号
    data = generate_ma_cross_signals(df)
    
    # 2. 计算标的资产每日收益率 (Close-to-Close)
    data['asset_return'] = data['close'].pct_change().fillna(0.0)
    
    # =========================================================================
    # 🚨 关键代码说明：【防未来函数 (Lookahead Bias) 的 shift(1) 设计】
    # -------------------------------------------------------------------------
    # `signal` 是在 T 日收盘后根据截至 T 日收盘价计算出的信号 (1 表示持仓, 0 表示空仓)。
    # 如果在 T 日收盘后得到买入信号，最快也只能在 T+1 日开盘/交易时执行持仓。
    # 因此，T+1 日的实际持仓状态 (position) 必须等于 T 日计算出的信号 (signal)。
    # 
    # 此处使用 `.shift(1)` 将信号整整下移 1 个交易日：
    #   position[T+1] = signal[T]
    # 
    # 这样用 `position[T+1] * asset_return[T+1]` 计算出来的每日收益率，
    # 才绝对不会偷看 T+1 日的收盘价，彻底避免了“未来函数”误导回测结果！
    # =========================================================================
    data['position'] = data['signal'].shift(1).fillna(0.0)
    
    # 3. 计算策略每日收益率
    data['strategy_return'] = data['position'] * data['asset_return']
    
    # 4. 计算策略与基准的累积净值 (Equity Curve)
    data['cum_asset_return'] = (1 + data['asset_return']).cumprod()
    data['cum_strategy_return'] = (1 + data['strategy_return']).cumprod()
    
    data['equity'] = initial_capital * data['cum_strategy_return']
    data['benchmark_equity'] = initial_capital * data['cum_asset_return']
    
    # 5. 计算回测绩效指标 (Performance Metrics)
    total_return = data['cum_strategy_return'].iloc[-1] - 1.0
    benchmark_return = data['cum_asset_return'].iloc[-1] - 1.0
    
    # 计算最大回撤 (Max Drawdown)
    cum_max = data['cum_strategy_return'].cummax()
    drawdown = (cum_max - data['cum_strategy_return']) / cum_max
    max_drawdown = drawdown.max()
    
    # 计算年化夏普比率 (Sharpe Ratio, 假设无风险利率为 0，每年 252 个交易日)
    daily_returns = data['strategy_return']
    if daily_returns.std() > 0:
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0

    metrics = {
        "初始资金": initial_capital,
        "最终资产": data['equity'].iloc[-1],
        "策略总收益率": f"{total_return * 100:.2f}%",
        "基准(买入持有)收益率": f"{benchmark_return * 100:.2f}%",
        "最大回撤": f"{max_drawdown * 100:.2f}%",
        "夏普比率": f"{sharpe_ratio:.2f}",
        "总交易日数": len(data)
    }
    
    return data, metrics

def plot_and_save_equity_curve(data: pd.DataFrame, symbol: str, name: str, output_path: str):
    """
    绘制并保存策略净值对比曲线图
    """
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'SimHei'] # 适配中文字体与标准字体
    plt.rcParams['axes.unicode_minus'] = False
    
    plt.figure(figsize=(12, 6))
    plt.plot(data['date'], data['cum_strategy_return'], label='Strategy (MA 5/10)', color='#1f77b4', linewidth=2)
    plt.plot(data['date'], data['cum_asset_return'], label=f'Benchmark Buy&Hold ({symbol})', color='#ff7f0e', linestyle='--', alpha=0.8)
    
    plt.title(f'Dual MA Backtest Equity Curve: {name} ({symbol})', fontsize=14, fontweight='bold')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Normalized Cumulative Return', fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(fontsize=11)
    plt.tight_layout()
    
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"📈 净值曲线图已保存至: {output_path}")

def run_single_stock_demo(symbol: str = "600519"):
    """
    对指定股票跑通完整回测演示
    """
    parquet_path = os.path.join(DATA_DIR, f"{symbol}.parquet")
    if not os.path.exists(parquet_path):
        raise FileNotFoundError(f"找不到数据文件 {parquet_path}，请先运行 data_fetch.py！")
        
    df = pd.read_parquet(parquet_path)
    stock_name = df['name'].iloc[0] if 'name' in df.columns else symbol
    
    result_df, metrics = run_vectorized_backtest(df)
    
    print("\n" + "="*50)
    print(f" 🚀 策略回测报告: {stock_name} ({symbol}) 🚀 ")
    print("="*50)
    for k, v in metrics.items():
        print(f"  • {k}: {v}")
    print("="*50)
    
    plot_path = os.path.join(DATA_DIR, f"equity_curve_{symbol}.png")
    plot_and_save_equity_curve(result_df, symbol, stock_name, plot_path)
    return result_df, metrics

if __name__ == "__main__":
    run_single_stock_demo()
