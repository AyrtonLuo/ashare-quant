"""
main.py
ashare-quant 量化研究系统一键研报自动化主入口 (阶段 5 全功能版)
全流程闭环：数据增量更新 -> 数据质量检测 -> 因子合成 -> IC诊断 -> 风控熔断 -> Alpha衰减诊断与系统健康报告
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.data_updater import update_incremental_stock_data
from src.data_quality import print_quality_report
from src.strategy.factors import calculate_raw_factors, preprocess_factors_cross_section
from src.strategy.composite_factor import build_composite_alpha_factor
from src.factor_analyzer import summarize_factor_ic, calculate_rank_ic, run_layered_backtest, plot_and_save_layered_backtest
from src.risk_manager import apply_risk_managed_backtest
from src.strategy_decay_analyzer import diagnose_alpha_decay

DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")


def plot_and_save_risk_managed_chart(data: pd.DataFrame, factor_name: str, output_path: str):
    """
    绘制无风控 vs 15% 回撤熔断风控后的净值对比图
    """
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    plt.figure(figsize=(12, 6))
    plt.plot(data['date'], data['cum_top'], label=f'Raw Strategy Top Group ({factor_name})', color='#1f77b4', linestyle='--', alpha=0.7)
    plt.plot(data['date'], data['cum_managed'], label=f'Risk Managed Strategy (15% MaxDD Circuit Breaker & 30% Cap)', color='#d62728', linewidth=2)
    plt.plot(data['date'], data['cum_benchmark'], label='Equal-Weighted Benchmark (10 Stocks)', color='#7f7f7f', linestyle=':', linewidth=1.5)
    
    # 标记熔断冷却状态区间
    broken_dates = data[data['in_circuit_breaker']]['date']
    if not broken_dates.empty:
        plt.axvspan(broken_dates.iloc[0], broken_dates.iloc[-1], color='orange', alpha=0.2, label='Circuit Breaker Active (Flat Cash)')

    plt.title(f'Risk Management & Circuit Breaker Backtest: {factor_name}', fontsize=13, fontweight='bold')
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
    print(" 🚀 启动 ashare-quant 多因子量化研究系统一键自动化闭环研报 🚀 ")
    print("=" * 85)
    
    # 步骤 1: 增量更新数据
    print("\n【步骤 1/5】检测与更新本地 Parquet 股票数据...")
    update_incremental_stock_data()
    
    # 步骤 2: 数据质量校验
    print("\n【步骤 2/5】进行数据质量审计与异常值校验...")
    print_quality_report()
    
    # 步骤 3: 因子计算与防未来动态合成
    print("\n【步骤 3/5】计算基础多因子与构建扩展窗口动态加权 Composite Alpha 因子...")
    parquet_path = os.path.join(DATA_DIR, "stocks_daily.parquet")
    raw_df = pd.read_parquet(parquet_path)
    
    df_factors = calculate_raw_factors(raw_df)
    df_factors['LOW_VOL_20'] = -df_factors['VOL_20']
    
    factor_base_names = ["MOM_20", "VOL_20", "LOW_VOL_20", "MA_DEV_20"]
    df_processed = preprocess_factors_cross_section(df_factors, factor_base_names)
    
    # 动态 IC-IR 权重合成
    df_composite = build_composite_alpha_factor(df_processed, method="dynamic_ic_ir")
    
    # 步骤 4: 因子 IC 诊断与分层回测
    print("\n【步骤 4/5】全因子 IC 诊断与周频分层回测...")
    all_factor_cols = ["MOM_20", "LOW_VOL_20", "MA_DEV_20", "COMPOSITE_ALPHA"]
    ic_summary = summarize_factor_ic(df_composite, all_factor_cols)
    
    print("\n" + "=" * 85)
    print(" 📋 多因子与复合 Alpha IC 检验诊断总览 📋 ")
    print("=" * 85)
    print(ic_summary.to_string(index=False))
    print("=" * 85)

    # 步骤 5: 组合风控熔断器与 Alpha 衰减诊断
    print("\n【步骤 5/5】应用组合风控熔断机制与 Alpha 衰减诊断闭环...")
    
    # 针对 Composite Alpha 运行分层回测与风控熔断
    res_df, raw_metrics = run_layered_backtest(df_composite, "COMPOSITE_ALPHA_norm")
    managed_df, risk_metrics = apply_risk_managed_backtest(res_df, max_dd_limit=0.15, cooldown_days=10, max_stock_weight=0.30)
    
    chart_path = os.path.join(DATA_DIR, "layered_backtest_risk_managed_COMPOSITE_ALPHA.png")
    plot_and_save_risk_managed_chart(managed_df, "COMPOSITE_ALPHA", chart_path)

    # Alpha 衰减诊断
    comp_ic_df = calculate_rank_ic(df_composite, "COMPOSITE_ALPHA_norm")
    decay_diag = diagnose_alpha_decay(comp_ic_df, "COMPOSITE_ALPHA")
    
    # 输出风控前后比对数据
    print("\n" + "=" * 85)
    print(" 🛡️ 组合风控熔断前后对比报告 🛡️ ")
    print("=" * 85)
    raw_top_ret = float(raw_metrics['Top 多头组总收益'].replace('%', '')) / 100.0
    cum_top = res_df['cum_top']
    raw_max_dd = ((cum_top.cummax() - cum_top) / cum_top.cummax()).max()
    
    print(f"{'指标名称':<20} | {'原始策略 (无风控)':<20} | {'风控熔断策略 (15% MaxDD & 30% Cap)':<30}")
    print("-" * 85)
    print(f"{'Top 多头组收益':<20} | {raw_top_ret*100:>18.2f}% | {risk_metrics['风控后总收益率']*100:>28.2f}%")
    print(f"{'最大回撤 (MaxDD)':<20} | {raw_max_dd*100:>18.2f}% | {risk_metrics['风控后最大回撤']*100:>28.2f}%")
    print(f"{'夏普比率 (Sharpe)':<20} | {'--':>19} | {risk_metrics['风控后夏普比率']:>29.2f}")
    print(f"{'熔断触发次数':<20} | {'0 次':>18} | {str(risk_metrics['熔断触发次数']) + ' 次':>28}")
    print("=" * 85)

    # 打印最终系统健康度与实盘部署建议报告
    print("\n" + "=" * 85)
    print(" 🩺 系统综合健康度与实盘部署建议报告 🩺 ")
    print("=" * 85)
    print(f"  • 因子状态: {decay_diag['status']}")
    print(f"  • 60日 Rolling IC: {decay_diag['rolling_ic_60']:.4f}")
    print(f"  • 诊断信息: {decay_diag['warning_msg']}")
    print(f"  • 组合风控状态: 已启用 (单股上限 30%, 15% 动态回撤强平冷静)")
    print(f"  • 熔断触发纪录: 共触发 {risk_metrics['熔断触发次数']} 次熔断保护")
    print("-" * 85)
    
    if decay_diag['is_decayed']:
        print("  ❌ 实盘部署建议: [暂停实盘 / 重新训练] - 因子出现 Alpha 衰减，建议进入迭代闭环重构因子！")
    else:
        print("  🟢 实盘部署建议: [适合模拟盘 / 试跑实盘] - 系统各项风控指标良好，模型具备强健的防护能力！")
    print("=" * 85)


if __name__ == "__main__":
    run_pipeline()
