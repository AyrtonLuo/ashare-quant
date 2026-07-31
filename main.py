"""
main.py
ashare-quant 量化研究系统一键研报主入口 (阶段 6 中大盘优质标的池版)
1. 全 A 股 90 亿+ 市值筛选、剔除 ST / 次新股
2. 多线程并发抓取与增量更新
3. 横截面 Top 5% 选股与多因子/复合 Alpha IC 检验诊断
4. 风控熔断与最新调仓日选股名单输出
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.data_updater import update_quality_universe_data
from src.data_quality import print_quality_report
from src.strategy.factors import calculate_raw_factors, preprocess_factors_cross_section
from src.strategy.composite_factor import build_composite_alpha_factor
from src.factor_analyzer import summarize_factor_ic, calculate_rank_ic, run_layered_backtest, plot_and_save_layered_backtest
from src.risk_manager import apply_risk_managed_backtest
from src.strategy_decay_analyzer import diagnose_alpha_decay

DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")


def plot_and_save_risk_managed_chart(data: pd.DataFrame, factor_name: str, output_path: str):
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    plt.figure(figsize=(12, 6))
    plt.plot(data['date'], data['cum_top'], label=f'Raw Strategy Top 5% ({factor_name})', color='#1f77b4', linestyle='--', alpha=0.7)
    plt.plot(data['date'], data['cum_managed'], label='Risk Managed Strategy (15% MaxDD Circuit Breaker & 30% Cap)', color='#d62728', linewidth=2)
    plt.plot(data['date'], data['cum_benchmark'], label='Equal-Weighted Benchmark (90B+ Universe)', color='#7f7f7f', linestyle=':', linewidth=1.5)
    
    broken_dates = data[data['in_circuit_breaker']]['date']
    if not broken_dates.empty:
        plt.axvspan(broken_dates.iloc[0], broken_dates.iloc[-1], color='orange', alpha=0.2, label='Circuit Breaker Active (Flat Cash)')

    plt.title(f'Risk Management & Circuit Breaker Backtest: 90B+ Universe ({factor_name})', fontsize=13, fontweight='bold')
    plt.xlabel('Date', fontsize=11)
    plt.ylabel('Normalized Equity', fontsize=11)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(fontsize=10)
    plt.tight_layout()
    
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"📈 组合风控熔断对比图已保存至: {output_path}")


def run_pipeline():
    print("=" * 85)
    print(" 🚀 启动 ashare-quant【90亿+ 中大盘优质标的池】多因子自动化研报 🚀 ")
    print("=" * 85)
    
    # 步骤 1: 筛选 90亿+ 优质标的池并多线程并发更新日线
    print("\n【步骤 1/5】筛选 90 亿+ 市值股票池 (剔除 ST/次新) 并并发更新日线...")
    raw_df = update_quality_universe_data(max_workers=8, end_date="20260731")
    
    num_universe_stocks = raw_df['symbol'].nunique()
    print(f"\n✅ 90 亿+ 优质标的池构建完成！涵盖 {num_universe_stocks} 只中大盘龙头股票。")
    
    # 步骤 2: 运行数据质量诊断
    print("\n【步骤 2/5】进行数据质量审计与异常值校验...")
    print_quality_report()
    
    # 步骤 3: 因子计算与防未来动态合成
    print("\n【步骤 3/5】计算基础多因子与构建防未来的 Composite Alpha 因子...")
    df_factors = calculate_raw_factors(raw_df)
    df_factors['LOW_VOL_20'] = -df_factors['VOL_20']
    
    factor_base_names = ["MOM_20", "VOL_20", "LOW_VOL_20", "MA_DEV_20"]
    df_processed = preprocess_factors_cross_section(df_factors, factor_base_names)
    
    # 扩展窗口动态 IC-IR 合成
    df_composite = build_composite_alpha_factor(df_processed, method="dynamic_ic_ir")
    
    # 步骤 4: 全因子 IC 诊断分析
    print("\n【步骤 4/5】全因子 IC 诊断分析...")
    all_factor_cols = ["MOM_20", "LOW_VOL_20", "MA_DEV_20", "COMPOSITE_ALPHA"]
    ic_summary = summarize_factor_ic(df_composite, all_factor_cols)
    
    print("\n" + "=" * 85)
    print(" 📋 90 亿+ 优质股票池全因子 IC 检验诊断总览 📋 ")
    print("=" * 85)
    print(ic_summary.to_string(index=False))
    print("=" * 85)

    # 步骤 5: 周频 Top 5% 分层回测、风控熔断与最新 Top 选股名单
    print("\n【步骤 5/5】Top 5% 周频分层回测、风控熔断与最新调仓日选股清单...")
    
    res_df, raw_metrics = run_layered_backtest(df_composite, "COMPOSITE_ALPHA_norm", rebalance_freq=5, top_pct=0.05)
    managed_df, risk_metrics = apply_risk_managed_backtest(res_df, max_dd_limit=0.15, cooldown_days=10, max_stock_weight=0.30)
    
    chart_path = os.path.join(DATA_DIR, "layered_backtest_risk_managed_COMPOSITE_ALPHA.png")
    plot_and_save_risk_managed_chart(managed_df, "COMPOSITE_ALPHA", chart_path)

    # Alpha 衰减诊断
    comp_ic_df = calculate_rank_ic(df_composite, "COMPOSITE_ALPHA_norm")
    decay_diag = diagnose_alpha_decay(comp_ic_df, "COMPOSITE_ALPHA")
    
    # 获取最新调仓日的 Top 5% 组合选股名单
    latest_date = df_composite['date'].max()
    latest_day_data = df_composite[df_composite['date'] == latest_date].dropna(subset=['COMPOSITE_ALPHA_norm'])
    top_5pct_k = max(1, int(len(latest_day_data) * 0.05))
    top_portfolio = latest_day_data.sort_values('COMPOSITE_ALPHA_norm', ascending=False).head(top_5pct_k)
    
    # 打印选股组合名单
    print("\n" + "=" * 85)
    print(f" 🎯 最新调仓日 ({latest_date.strftime('%Y-%m-%d')}) Top 5% 优质组合选股名单 (共 {len(top_portfolio)} 只) 🎯 ")
    print("=" * 85)
    print(top_portfolio[['symbol', 'name', 'close', 'COMPOSITE_ALPHA_norm', 'MOM_20_norm', 'LOW_VOL_20_norm']].to_string(index=False))
    print("=" * 85)

    # 输出风控前后比对数据
    print("\n" + "=" * 85)
    print(" 🛡️ 90亿+ 优质标的池组合风控熔断前后对比报告 🛡️ ")
    print("=" * 85)
    raw_top_ret = float(raw_metrics['Top 多头组总收益'].replace('%', '')) / 100.0
    cum_top = res_df['cum_top']
    raw_max_dd = ((cum_top.cummax() - cum_top) / cum_top.cummax()).max()
    
    print(f"{'指标名称':<20} | {'原始 Top 5% 策略 (无风控)':<22} | {'风控熔断策略 (15% MaxDD & 30% Cap)':<30}")
    print("-" * 85)
    print(f"{'Top 多头组收益':<20} | {raw_top_ret*100:>20.2f}% | {risk_metrics['风控后总收益率']*100:>28.2f}%")
    print(f"{'最大回撤 (MaxDD)':<20} | {raw_max_dd*100:>20.2f}% | {risk_metrics['风控后最大回撤']*100:>28.2f}%")
    print(f"{'夏普比率 (Sharpe)':<20} | {'--':>21} | {risk_metrics['风控后夏普比率']:>29.2f}")
    print(f"{'熔断触发次数':<20} | {'0 次':>20} | {str(risk_metrics['熔断触发次数']) + ' 次':>28}")
    print("=" * 85)

    # 打印最终系统健康度与实盘部署建议报告
    print("\n" + "=" * 85)
    print(" 🩺 系统综合健康度与实盘部署建议报告 🩺 ")
    print("=" * 85)
    print(f"  • 优质股票池规模: {num_universe_stocks} 只 (总市值 >= 90亿元 & 剔除ST/次新)")
    print(f"  • 因子状态: {decay_diag['status']}")
    print(f"  • 60日 Rolling IC: {decay_diag['rolling_ic_60']:.4f}")
    print(f"  • 诊断信息: {decay_diag['warning_msg']}")
    print(f"  • 组合风控状态: 已启用 (Top 5% 选股, 单股上限 30%, 15% 动态回撤强平冷静)")
    print(f"  • 熔断触发纪录: 共触发 {risk_metrics['熔断触发次数']} 次熔断保护")
    print("-" * 85)
    
    if decay_diag['is_decayed']:
        print("  ❌ 实盘部署建议: [暂停实盘 / 重新训练] - 因子出现 Alpha 衰减，建议进入迭代闭环重构因子！")
    else:
        print("  🟢 实盘部署建议: [适合模拟盘 / 试跑实盘] - 系统各项风控指标良好，90亿+标的池保障极佳流动性与安全性！")
    print("=" * 85)

if __name__ == "__main__":
    run_pipeline()
