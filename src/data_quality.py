"""
data_quality.py
数据质量检查模块：检测 A 股日线 parquet 数据中的缺失值、极值以及因停牌导致的开盘交易日缺口。
"""

import os
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def check_data_quality(file_path: str = None) -> pd.DataFrame:
    """
    检查单个或汇总 parquet 文件的数据质量
    """
    if file_path is None:
        file_path = os.path.join(DATA_DIR, "stocks_daily.parquet")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}，请先运行 data_fetch.py 抓取数据！")

    df = pd.read_parquet(file_path)
    print(f"📊 正在对【{os.path.basename(file_path)}】进行数据质量检查 (总记录数: {len(df)} 条)...")

    results = []

    # 按股票分组检查
    for (symbol, name), group in df.groupby(['symbol', 'name']):
        group = group.sort_values('date').reset_index(drop=True)
        total_rows = len(group)
        
        # 1. 检查空值 (NaN)
        missing_count = group[['open', 'high', 'low', 'close', 'volume']].isnull().sum().sum()
        
        # 2. 检查价格异常 (如 0 或负数价格)
        invalid_price_count = (group[['open', 'high', 'low', 'close']] <= 0).sum().sum()
        
        # 3. 检查零成交量交易日 (通常为停牌/无流动性)
        zero_volume_count = (group['volume'] == 0).sum()
        
        # 4. 检查交易日日期间隔 (大于 4 天视为跨周末/长假之外的停牌缺口)
        group['date_diff'] = group['date'].diff().dt.days
        # 一般长假最长 7-9 天，若出现 > 10 天的大缺口则记录为潜在长时间停牌缺口
        large_gaps = group[group['date_diff'] > 10]
        gap_count = len(large_gaps)
        
        start_date = group['date'].min().strftime('%Y-%m-%d')
        end_date = group['date'].max().strftime('%Y-%m-%d')
        
        results.append({
            "股票代码": symbol,
            "股票名称": name,
            "起始日期": start_date,
            "结束日期": end_date,
            "总交易日数": total_rows,
            "缺失值数量": missing_count,
            "异常价格数": invalid_price_count,
            "零成交日数": zero_volume_count,
            "长停牌缺口数": gap_count
        })

    report_df = pd.DataFrame(results)
    return report_df

def print_quality_report():
    report_df = check_data_quality()
    print("\n" + "="*80)
    print(" 📋 数据质量诊断报告 📋 ")
    print("="*80)
    print(report_df.to_string(index=False))
    print("="*80)
    
    # 总结说明
    total_missing = report_df["缺失值数量"].sum()
    total_invalid = report_df["异常价格数"].sum()
    
    if total_missing == 0 and total_invalid == 0:
        print("✅ 数据质量优秀：未发现任何字段缺失或价格异常值。")
    else:
        print(f"⚠️ 警告：检测到 {total_missing} 处缺失值与 {total_invalid} 处价格异常，请处理后使用！")
    return report_df

if __name__ == "__main__":
    print_quality_report()
