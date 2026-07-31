"""
main.py
ashare-quant 量化研究系统一键研报自动化主入口
全流程联动：数据增量更新 -> 数据质量检测 -> 因子计算与复合 Alpha 合成 -> IC 检验分析 -> 周频分层回测
"""

import os
import sys
import pandas as pd

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.data_updater import update_incremental_stock_data
from src.data_quality import print_quality_report
from src.strategy.factors import calculate_raw_factors, preprocess_factors_cross_section
from src.strategy.composite_factor import build_composite_alpha_factor
from src.factor_analyzer import summarize_factor_ic, run_layered_backtest, plot_and_save_layered_backtest

DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")


def run_pipeline():
    print("=" * 85)
    print(" 🚀 启动 ashare-quant 多因子量化研究系统一键自动化研报 🚀 ")
    print("=" * 85)
    
    # 步骤 1: 运行数据增量更新管道
    print("\n【步骤 1/4】检测与更新本地 Parquet 股票数据...")
    update_incremental_stock_data()
    
    # 步骤 2: 运行数据质量诊断
    print("\n【步骤 2/4】进行数据质量审计与异常值校验...")
    print_quality_report()
    
    # 步骤 3: 因子计算、动态权重合成 Composite Alpha 因子
    print("\n【步骤 3/4】计算基础多因子与构建防未来的复合 Alpha 因子...")
    parquet_path = os.path.join(DATA_DIR, "stocks_daily.parquet")
    raw_df = pd.read_parquet(parquet_path)
    
    df_factors = calculate_raw_factors(raw_df)
    df_factors['LOW_VOL_20'] = -df_factors['VOL_20']
    
    factor_base_names = ["MOM_20", "VOL_20", "LOW_VOL_20", "MA_DEV_20"]
    df_processed = preprocess_factors_cross_section(df_factors, factor_base_names)
    
    # 采用防未来的扩展历史 IC-IR 动态加权合成复合 Alpha 因子
    df_composite = build_composite_alpha_factor(df_processed, method="dynamic_ic_ir")
    
    # 步骤 4: IC 诊断报告与周频分层回测
    print("\n【步骤 4/4】生成全因子 IC 诊断分析与周频分层回测报告...")
    all_factor_cols = ["MOM_20", "LOW_VOL_20", "MA_DEV_20", "COMPOSITE_ALPHA"]
    
    ic_summary = summarize_factor_ic(df_composite, all_factor_cols)
    print("\n" + "=" * 85)
    print(" 📋 多因子与复合 Alpha IC 检验诊断总览 📋 ")
    print("=" * 85)
    print(ic_summary.to_string(index=False))
    print("=" * 85)
    
    # 运行分层回测对比 (单因子 vs 复合 Alpha)
    comparison_results = []
    
    for factor in ["MOM_20", "LOW_VOL_20", "COMPOSITE_ALPHA"]:
        norm_col = f"{factor}_norm"
        res_df, metrics = run_layered_backtest(df_composite, norm_col)
        
        chart_path = os.path.join(DATA_DIR, f"layered_backtest_{factor}.png")
        plot_and_save_layered_backtest(res_df, factor, chart_path)
        
        # 获取该因子的 IC IR
        factor_ic_row = ic_summary[ic_summary['因子名称'] == factor]
        ic_ir_val = factor_ic_row['IC 信息比率 (IC IR)'].values[0] if not factor_ic_row.empty else 0.0
        
        # 计算 Top 组回测的真实最大回撤
        cum_top = res_df['cum_top']
        cum_max = cum_top.cummax()
        max_dd = ((cum_max - cum_top) / cum_max).max()
        
        comparison_results.append({
            "因子类别": "复合因子" if factor.startswith("COMPOSITE") else "单因子",
            "因子名称": factor,
            "IC IR": f"{ic_ir_val:.4f}",
            "Top 组总收益": metrics["Top 多头组总收益"],
            "Top 组超额收益": metrics["Top 超额收益"],
            "Top 组最大回撤": f"{max_dd * 100:.2f}%"
        })

    comp_df = pd.DataFrame(comparison_results)
    print("\n" + "=" * 85)
    print(" 🏆 单因子 vs 复合 Alpha 因子回测与风险对比报告 🏆 ")
    print("=" * 85)
    print(comp_df.to_string(index=False))
    print("=" * 85)
    
    print("\n🎉 一键量化研报自动化生成完毕！所有对比图表与数据均已更新在 data/ 目录。")

if __name__ == "__main__":
    run_pipeline()
