"""
factor_analyzer.py
因子检验与分层回测分析引擎：包含 Rank IC / IC IR 诊断分析与周频分层回测模块。
"""

import os
import sys
import pandas as pd
import numpy as np
import scipy.stats as stats
import matplotlib.pyplot as plt

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.strategy.factors import calculate_raw_factors, preprocess_factors_cross_section

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def calculate_rank_ic(df: pd.DataFrame, factor_col: str) -> pd.DataFrame:
    """
    计算每日横截面 Rank IC (Spearman 秩相关系数)
    
    ===========================================================================
    🚨 【未来 1 日收益率严格对齐逻辑 (Forward Return Alignment)】:
    第 T 日的因子值 X_T 表示截至第 T 日收盘结算出的因子表现。
    为了检验因子对未来价格的预测能力，必须匹配股票在第 T+1 日的真实收益率 (Forward Return)。
    此处 `forward_return_1d` 在第 T 行存储的是 `(close_{T+1} - close_T) / close_T`。
    计算第 T 日的 SpearmanRankCorr(factor_T, forward_return_1d_T)，
    保证了第 T 日计算因子时绝不偷看未来价格，逻辑严格防未来函数！
    ===========================================================================
    """
    data = df.copy()
    data = data.sort_values(['symbol', 'date']).reset_index(drop=True)
    
    # 严格对齐 T+1 未来 1 日收益率
    data['forward_return_1d'] = data.groupby('symbol')['close'].transform(lambda s: s.shift(-1) / s - 1.0)
    
    ic_list = []
    
    for date, group in data.groupby('date'):
        valid = group[[factor_col, 'forward_return_1d']].dropna()
        # 横截面有效样本数需 >= 3 才能计算有意义的秩相关
        if len(valid) >= 3:
            rank_ic, p_val = stats.spearmanr(valid[factor_col], valid['forward_return_1d'])
            if not np.isnan(rank_ic):
                ic_list.append({
                    "date": date,
                    "rank_ic": rank_ic,
                    "p_value": p_val
                })
                
    return pd.DataFrame(ic_list)


def summarize_factor_ic(df: pd.DataFrame, factor_cols: list[str]) -> pd.DataFrame:
    """
    对多个因子汇总计算 IC Mean, IC Std, IC IR, IC 胜率 (IC > 0 Ratio)
    """
    summary = []
    
    for factor in factor_cols:
        norm_col = f"{factor}_norm"
        ic_df = calculate_rank_ic(df, norm_col)
        
        if ic_df.empty:
            continue
            
        ic_series = ic_df['rank_ic']
        ic_mean = ic_series.mean()
        ic_std = ic_series.std()
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0
        ic_win_ratio = (ic_series > 0).mean()
        
        summary.append({
            "因子名称": factor,
            "IC 均值 (IC Mean)": ic_mean,
            "IC 标准差 (IC Std)": ic_std,
            "IC 信息比率 (IC IR)": ic_ir,
            "IC 胜率 (IC > 0)": f"{ic_win_ratio * 100:.2f}%",
            "有效交易日数": len(ic_df)
        })
        
    return pd.DataFrame(summary)


def run_layered_backtest(df: pd.DataFrame, factor_col: str, rebalance_freq: int = 5, top_pct: float = 0.05) -> tuple[pd.DataFrame, dict]:
    """
    运行周频 (每 5 个交易日) 分层回测 (Top 组 5% vs Bottom 组 5% vs Benchmark 等权)
    """
    data = df.copy()
    data = data.sort_values(['date', 'symbol']).reset_index(drop=True)
    
    # 提取所有不重复交易日
    unique_dates = data['date'].drop_duplicates().sort_values().reset_index(drop=True)
    
    daily_returns_list = []
    
    top_stocks = []
    bottom_stocks = []
    
    for i in range(len(unique_dates) - 1):
        curr_date = unique_dates.iloc[i]
        next_date = unique_dates.iloc[i + 1]
        
        # 判断是否为调仓日 (每 rebalance_freq 天调仓一次)
        if i % rebalance_freq == 0:
            day_data = data[data['date'] == curr_date].dropna(subset=[factor_col])
            num_valid = len(day_data)
            if num_valid >= 10:
                top_k = max(1, int(num_valid * top_pct))
                # 排序选取得分最高前 5% 与最低前 5%
                sorted_day = day_data.sort_values(factor_col, ascending=False)
                top_stocks = sorted_day['symbol'].iloc[:top_k].tolist()
                bottom_stocks = sorted_day['symbol'].iloc[-top_k:].tolist()
        
        # 计算下一个交易日各持仓组的日收益率
        next_day_data = data[data['date'] == next_date]
        if next_day_data.empty:
            continue
            
        next_day_data = next_day_data.set_index('symbol')
        
        # 全集等权基准日收益
        bench_ret = next_day_data['asset_return'].mean()
        
        # Top 组日收益
        top_valid = [s for s in top_stocks if s in next_day_data.index]
        top_ret = next_day_data.loc[top_valid, 'asset_return'].mean() if top_valid else 0.0
        
        # Bottom 组日收益
        bottom_valid = [s for s in bottom_stocks if s in next_day_data.index]
        bottom_ret = next_day_data.loc[bottom_valid, 'asset_return'].mean() if bottom_valid else 0.0
        
        daily_returns_list.append({
            "date": next_date,
            "top_return": top_ret,
            "bottom_return": bottom_ret,
            "benchmark_return": bench_ret
        })
        
    res_df = pd.DataFrame(daily_returns_list)
    res_df['cum_top'] = (1 + res_df['top_return'].fillna(0.0)).cumprod()
    res_df['cum_bottom'] = (1 + res_df['bottom_return'].fillna(0.0)).cumprod()
    res_df['cum_benchmark'] = (1 + res_df['benchmark_return'].fillna(0.0)).cumprod()
    
    # 超额收益曲线 (Top 净值 / Benchmark 净值)
    res_df['excess_equity'] = res_df['cum_top'] / res_df['cum_benchmark']
    
    total_top_return = res_df['cum_top'].iloc[-1] - 1.0
    total_bench_return = res_df['cum_benchmark'].iloc[-1] - 1.0
    excess_return = res_df['excess_equity'].iloc[-1] - 1.0
    
    metrics = {
        "Top 多头组总收益": f"{total_top_return * 100:.2f}%",
        "Benchmark 基准收益": f"{total_bench_return * 100:.2f}%",
        "Top 超额收益": f"{excess_return * 100:.2f}%"
    }
    
    return res_df, metrics


def plot_and_save_layered_backtest(res_df: pd.DataFrame, factor_name: str, output_path: str):
    """
    绘制分层回测净值曲线与超额收益曲线图
    """
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
    
    # 上图：Top 组 vs Bottom 组 vs Benchmark 净值
    ax1.plot(res_df['date'], res_df['cum_top'], label=f'Top Group (Best {factor_name})', color='#d62728', linewidth=2)
    ax1.plot(res_df['date'], res_df['cum_bottom'], label=f'Bottom Group (Worst {factor_name})', color='#2ca02c', linestyle='--', alpha=0.8)
    ax1.plot(res_df['date'], res_df['cum_benchmark'], label='Equal-Weighted Benchmark (10 Stocks)', color='#7f7f7f', linestyle=':', linewidth=1.5)
    ax1.set_title(f'Layered Backtest Equity Curve (Factor: {factor_name})', fontsize=13, fontweight='bold')
    ax1.set_ylabel('Normalized Equity', fontsize=11)
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(fontsize=10)
    
    # 下图：Top 组相对于 Benchmark 的超额收益净值
    ax2.plot(res_df['date'], res_df['excess_equity'], label='Top Group Excess Equity (Top / Bench)', color='#1f77b4', linewidth=2)
    ax2.axhline(1.0, color='black', linestyle='--', alpha=0.5)
    ax2.set_title('Top Group Excess Return vs Benchmark', fontsize=11)
    ax2.set_xlabel('Date', fontsize=11)
    ax2.set_ylabel('Excess Equity', fontsize=11)
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend(fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"📈 因子【{factor_name}】分层回测净值图已保存至: {output_path}")


def run_full_factor_analysis():
    """
    运行全流程多因子计算、IC 诊断与分层回测
    """
    parquet_path = os.path.join(DATA_DIR, "stocks_daily.parquet")
    if not os.path.exists(parquet_path):
        raise FileNotFoundError(f"找不到 {parquet_path}，请先运行 data_fetch.py！")
        
    raw_df = pd.read_parquet(parquet_path)
    print("📊 正在计算 10 只成分股的基础多因子...")
    
    # 1. 计算原始因子
    df_factors = calculate_raw_factors(raw_df)
    
    # 低波动因子 (低波动率异常：取 VOL_20 的相反数)
    df_factors['LOW_VOL_20'] = -df_factors['VOL_20']
    
    factor_names = ["MOM_20", "VOL_20", "LOW_VOL_20", "MA_DEV_20"]
    
    # 2. 因子 MAD 去极值与 Z-Score 标准化
    df_processed = preprocess_factors_cross_section(df_factors, factor_names)
    
    # 3. 输出 Rank IC 检验诊断报告
    print("\n" + "="*85)
    print(" 📋 基础多因子 IC 检验诊断报告 (Rank IC) 📋 ")
    print("="*85)
    ic_summary = summarize_factor_ic(df_processed, factor_names)
    print(ic_summary.to_string(index=False))
    print("="*85)
    
    # 4. 对所有因子运行周频分层回测
    print("\n🚀 正在对各因子运行周频 (5日) 分层回测...")
    layered_summary = []
    
    for factor in ["MOM_20", "LOW_VOL_20", "MA_DEV_20"]:
        norm_factor = f"{factor}_norm"
        res_df, metrics = run_layered_backtest(df_processed, norm_factor)
        
        chart_path = os.path.join(DATA_DIR, f"layered_backtest_{factor}.png")
        plot_and_save_layered_backtest(res_df, factor, chart_path)
        
        layered_summary.append({
            "因子名称": factor,
            "Top 多头组收益": metrics["Top 多头组总收益"],
            "Benchmark 基准收益": metrics["Benchmark 基准收益"],
            "Top 超额收益": metrics["Top 超额收益"]
        })

    print("\n" + "="*70)
    print(" 🏆 多因子周频分层回测超额收益对比总览 🏆 ")
    print("="*70)
    print(pd.DataFrame(layered_summary).to_string(index=False))
    print("="*70)
    
    return df_processed, ic_summary


if __name__ == "__main__":
    run_full_factor_analysis()
