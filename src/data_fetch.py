"""
data_fetch.py
数据获取模块：从 akshare 获取沪深300精选成分股的前复权日线数据并保存为 Parquet 文件。
"""

import os
import pandas as pd
import akshare as ak
from datetime import datetime

# 选取的 10 只经典沪深300成分股（涵盖白酒、金融、新能源、资源、家电等龙头）
TARGET_STOCKS = [
    {"symbol": "600519", "name": "贵州茅台"},
    {"symbol": "601318", "name": "中国平安"},
    {"symbol": "300750", "name": "宁德时代"},
    {"symbol": "000001", "name": "平安银行"},
    {"symbol": "600036", "name": "招商银行"},
    {"symbol": "002594", "name": "比亚迪"},
    {"symbol": "601899", "name": "紫金矿业"},
    {"symbol": "600900", "name": "长江电力"},
    {"symbol": "601012", "name": "隆基绿能"},
    {"symbol": "000651", "name": "格力电器"},
]

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def fetch_stock_daily(symbol: str, start_date: str = "20230101", end_date: str = "20260101", adjust: str = "qfq") -> pd.DataFrame:
    """
    通过 akshare 获取单只股票前复权日线数据
    """
    print(f"正在抓取股票代码: {symbol} (复权类型: {adjust}, 时间: {start_date} ~ {end_date})...")
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust=adjust
    )
    
    if df.empty:
        raise ValueError(f"未获取到股票 {symbol} 的数据！")

    # 统一列名映射
    column_mapping = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude",
        "涨跌幅": "pct_chg",
        "涨跌额": "change",
        "换手率": "turnover"
    }
    df = df.rename(columns=column_mapping)
    
    # 类型转换与过滤列
    df['date'] = pd.to_datetime(df['date'])
    df['symbol'] = symbol
    
    required_cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'amount']
    df = df[required_cols].sort_values('date').reset_index(drop=True)
    return df

def fetch_and_save_all(start_date: str = "20230101", end_date: str = "20260101"):
    """
    批量获取所有目标股票数据并保存为 Parquet 文件
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    all_dfs = []

    for stock in TARGET_STOCKS:
        sym = stock["symbol"]
        name = stock["name"]
        try:
            df = fetch_stock_daily(symbol=sym, start_date=start_date, end_date=end_date)
            df['name'] = name
            
            # 单独保存单只股票 Parquet
            single_path = os.path.join(DATA_DIR, f"{sym}.parquet")
            df.to_parquet(single_path, index=False)
            print(f"  ✓ {name}({sym}) 成功保存至 {single_path} (共 {len(df)} 条记录)")
            
            all_dfs.append(df)
        except Exception as e:
            print(f"  ✗ 获取股票 {name}({sym}) 失败: {e}")

    if all_dfs:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        combined_path = os.path.join(DATA_DIR, "stocks_daily.parquet")
        combined_df.to_parquet(combined_path, index=False)
        print(f"\n🎉 汇总数据保存成功: {combined_path} (共 {len(combined_df)} 条记录，涵盖 {len(all_dfs)} 只股票)")

if __name__ == "__main__":
    fetch_and_save_all()
