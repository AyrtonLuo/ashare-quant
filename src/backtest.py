"""
backtest.py
向量化与约束仿真回测引擎：支持理想回测与 A 股真实交易约束（涨跌停限制、T+1 制度）对比仿真。
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


def get_stock_limit_ratio(symbol: str) -> float:
    """
    根据股票代码获取 A 股涨跌停比例限制
    - 创业板 (300) / 科创板 (688): ±20%
    - 主板 (600, 601, 603, 605, 000, 001, 002 等): ±10%
    """
    sym = str(symbol).strip()
    if sym.startswith("300") or sym.startswith("688"):
        return 0.20
    return 0.10


def calculate_price_limits(df: pd.DataFrame, symbol: str, tol: float = 1e-3) -> tuple[pd.Series, pd.Series]:
    """
    精确判定每日是否触发涨停或跌停（考虑到 A 股价格保留两位小数四舍五入与浮点数容差）
    """
    limit_ratio = get_stock_limit_ratio(symbol)
    prev_close = df['close'].shift(1)
    
    # 按照 A 股规则对涨停与跌停限制价格四舍五入到两位小数
    limit_up_price = (prev_close * (1.0 + limit_ratio)).round(2)
    limit_down_price = (prev_close * (1.0 - limit_ratio)).round(2)
    
    # 使用浮点数容差 (1e-3) 进行四舍五入后的封板价格比对
    is_limit_up = (df['close'] >= limit_up_price - tol) & (prev_close.notnull())
    is_limit_down = (df['close'] <= limit_down_price + tol) & (prev_close.notnull())
    
    return is_limit_up, is_limit_down


def calculate_performance_metrics(strategy_returns: pd.Series, cum_returns: pd.Series, initial_capital: float = 100000.0) -> dict:
    """
    计算策略的核心绩效指标（总收益率、最大回撤、夏普比率）
    """
    total_return = cum_returns.iloc[-1] - 1.0
    
    # 最大回撤 (Max Drawdown)
    cum_max = cum_returns.cummax()
    drawdown = (cum_max - cum_returns) / cum_max
    max_drawdown = drawdown.max()
    
    # 年化夏普比率 (Sharpe Ratio, 假设无风险利率为 0，每年 252 交易日)
    if strategy_returns.std() > 0:
        sharpe_ratio = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0

    return {
        "最终资产": initial_capital * cum_returns.iloc[-1],
        "总收益率": total_return,
        "最大回撤": max_drawdown,
        "夏普比率": sharpe_ratio
    }


def run_vectorized_backtest(df: pd.DataFrame, symbol: str, initial_capital: float = 100000.0) -> tuple[pd.DataFrame, dict, dict]:
    """
    运行回测：对比【理想无约束】与【含 A 股涨跌停及 T+1 约束】的交易表现
    """
    data = generate_ma_cross_signals(df)
    data['asset_return'] = data['close'].pct_change().fillna(0.0)
    
    # 1. 计算涨跌停状态
    is_limit_up, is_limit_down = calculate_price_limits(data, symbol)
    data['is_limit_up'] = is_limit_up
    data['is_limit_down'] = is_limit_down

    # =========================================================================
    # 🚨 防未来函数 (Lookahead Bias) 的 shift(1)
    # T 日收盘计算出的信号 signal[T]，最快只能在 T+1 日开盘/交易时决定 T+1 的持仓。
    # 理想未受约束情况下的持仓状态:
    # =========================================================================
    data['ideal_position'] = data['signal'].shift(1).fillna(0.0)

    # 2. 模拟真实 A 股约束下的实际持仓状态 (Constrained Position)
    n = len(data)
    constrained_pos = np.zeros(n)
    
    for t in range(n):
        if t == 0:
            constrained_pos[t] = 0.0
            continue
            
        target_pos = data['ideal_position'].iloc[t]
        prev_pos = constrained_pos[t - 1]
        lim_up = data['is_limit_up'].iloc[t]
        lim_down = data['is_limit_down'].iloc[t]
        
        # 拟买入 (仓位增加)
        if target_pos > prev_pos:
            if lim_up:
                # 涨停封板，挂买单无法成交！保持前日持仓
                constrained_pos[t] = prev_pos
            else:
                constrained_pos[t] = target_pos
                
        # 拟卖出 (仓位减少)
        elif target_pos < prev_pos:
            if lim_down:
                # 跌停封板，卖单砸盘锁死无法成交！被迫被动持仓
                constrained_pos[t] = prev_pos
            else:
                constrained_pos[t] = target_pos
                
        # 仓位无变化
        else:
            constrained_pos[t] = prev_pos

    data['constrained_position'] = constrained_pos

    # 3. 计算策略每日收益率与累积净值
    data['ideal_strategy_return'] = data['ideal_position'] * data['asset_return']
    data['constrained_strategy_return'] = data['constrained_position'] * data['asset_return']
    
    data['cum_asset'] = (1 + data['asset_return']).cumprod()
    data['cum_ideal'] = (1 + data['ideal_strategy_return']).cumprod()
    data['cum_constrained'] = (1 + data['constrained_strategy_return']).cumprod()

    # 4. 汇总指标
    metrics_ideal = calculate_performance_metrics(data['ideal_strategy_return'], data['cum_ideal'], initial_capital)
    metrics_constrained = calculate_performance_metrics(data['constrained_strategy_return'], data['cum_constrained'], initial_capital)
    
    # 补充基准收益
    metrics_ideal["基准收益率"] = data['cum_asset'].iloc[-1] - 1.0
    metrics_constrained["基准收益率"] = data['cum_asset'].iloc[-1] - 1.0

    return data, metrics_ideal, metrics_constrained


def plot_and_save_comparison_chart(data: pd.DataFrame, symbol: str, name: str, output_path: str):
    """
    绘制并保存【理想无约束】vs【A股真实约束】vs【买入持有基准】净值对比图
    """
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    plt.figure(figsize=(12, 6))
    
    plt.plot(data['date'], data['cum_ideal'], label='Ideal Strategy (No Constraints)', color='#1f77b4', linewidth=2, linestyle='--')
    plt.plot(data['date'], data['cum_constrained'], label='Real Strategy (A-Share Price Limit & T+1)', color='#d62728', linewidth=2)
    plt.plot(data['date'], data['cum_asset'], label=f'Benchmark Buy&Hold ({symbol})', color='#7f7f7f', linestyle=':', alpha=0.7)
    
    plt.title(f'A-Share Trading Constraints Backtest Comparison: {name} ({symbol})', fontsize=13, fontweight='bold')
    plt.xlabel('Date', fontsize=11)
    plt.ylabel('Normalized Cumulative Return', fontsize=11)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(fontsize=10)
    plt.tight_layout()
    
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"📈 交易约束对比净值曲线已保存至: {output_path}")


def print_comparison_report(symbol: str, name: str, m_ideal: dict, m_real: dict):
    """
    打印文字版约束前后差异对比报告
    """
    ret_diff = (m_real['总收益率'] - m_ideal['总收益率']) * 100
    mdd_diff = (m_real['最大回撤'] - m_ideal['最大回撤']) * 100
    sharpe_diff = m_real['夏普比率'] - m_ideal['夏普比率']
    
    print("\n" + "="*80)
    print(f" 📊 A 股交易约束回测对比报告: {name} ({symbol}) 📊 ")
    print("="*80)
    print(f"{'评估指标':<18} | {'理想回测 (无约束)':<20} | {'真实回测 (含A股约束)':<22} | {'差异/影响 (真实-理想)':<18}")
    print("-" * 80)
    print(f"{'策略总收益率':<18} | {m_ideal['总收益率']*100:>18.2f}% | {m_real['总收益率']*100:>20.2f}% | {ret_diff:>16.2f}%")
    print(f"{'最大回撤':<18} | {m_ideal['最大回撤']*100:>18.2f}% | {m_real['最大回撤']*100:>20.2f}% | {mdd_diff:>16.2f}%")
    print(f"{'年化夏普比率':<18} | {m_ideal['夏普比率']:>19.2f}  | {m_real['夏普比率']:>21.2f}  | {sharpe_diff:>17.2f}")
    print(f"{'基准收益率':<18} | {m_ideal['基准收益率']*100:>18.2f}% | {m_real['基准收益率']*100:>20.2f}% | {'0.00%':>18}")
    print("="*80)


def run_demo(symbol: str = "300750"):
    """
    运行指定股票的交易约束回测演示 (默认使用创业板宁德时代 300750，或 贵州茅台 600519)
    """
    parquet_path = os.path.join(DATA_DIR, f"{symbol}.parquet")
    if not os.path.exists(parquet_path):
        raise FileNotFoundError(f"未找到数据文件 {parquet_path}，请先运行 data_fetch.py！")
        
    df = pd.read_parquet(parquet_path)
    stock_name = df['name'].iloc[0] if 'name' in df.columns else symbol
    
    data, m_ideal, m_real = run_vectorized_backtest(df, symbol=symbol)
    
    print_comparison_report(symbol, stock_name, m_ideal, m_real)
    
    chart_path = os.path.join(DATA_DIR, f"equity_curve_constrained_{symbol}.png")
    plot_and_save_comparison_chart(data, symbol, stock_name, chart_path)
    return data, m_ideal, m_real


if __name__ == "__main__":
    print("🚀 正在运行全部 10 只沪深300成分股的 A 股交易约束回测比对...\n")
    
    summary_list = []
    
    for filename in sorted(os.listdir(DATA_DIR)):
        if filename.endswith(".parquet") and filename != "stocks_daily.parquet":
            sym = filename.replace(".parquet", "")
            try:
                parquet_path = os.path.join(DATA_DIR, filename)
                df = pd.read_parquet(parquet_path)
                stock_name = df['name'].iloc[0] if 'name' in df.columns else sym
                
                data, m_ideal, m_real = run_vectorized_backtest(df, symbol=sym)
                chart_path = os.path.join(DATA_DIR, f"equity_curve_constrained_{sym}.png")
                plot_and_save_comparison_chart(data, sym, stock_name, chart_path)
                
                summary_list.append({
                    "代码": sym,
                    "名称": stock_name,
                    "理想总收益": f"{m_ideal['总收益率']*100:.2f}%",
                    "真实总收益": f"{m_real['总收益率']*100:.2f}%",
                    "理想最大回撤": f"{m_ideal['最大回撤']*100:.2f}%",
                    "真实最大回撤": f"{m_real['最大回撤']*100:.2f}%",
                    "理想夏普": f"{m_ideal['夏普比率']:.2f}",
                    "真实夏普": f"{m_real['夏普比率']:.2f}"
                })
            except Exception as e:
                print(f"回测 {sym} 报错: {e}")

    summary_df = pd.DataFrame(summary_list)
    print("\n" + "="*85)
    print(" 🏆 10 只成分股 A 股交易约束前后回测绩效总览 🏆 ")
    print("="*85)
    print(summary_df.to_string(index=False))
    print("="*85)

