"""
data_fetch.py
数据获取模块：获取沪深300精选成分股的前复权日线数据并保存为 Parquet 文件。
推荐并使用新浪/东财接口自动回退机制，确保抓取 100% 稳健可靠。
"""

import os
import time
import pandas as pd
import akshare as ak

# 选取的 10 只经典沪深300成分股
TARGET_STOCKS = [
    {"symbol": "600519", "prefix": "sh600519", "name": "贵州茅台"},
    {"symbol": "601318", "prefix": "sh601318", "name": "中国平安"},
    {"symbol": "300750", "prefix": "sz300750", "name": "宁德时代"},
    {"symbol": "000001", "prefix": "sz000001", "name": "平安银行"},
    {"symbol": "600036", "prefix": "sh600036", "name": "招商银行"},
    {"symbol": "002594", "prefix": "sz002594", "name": "比亚迪"},
    {"symbol": "601899", "prefix": "sh601899", "name": "紫金矿业"},
    {"symbol": "600900", "prefix": "sh600900", "name": "长江电力"},
    {"symbol": "601012", "prefix": "sh601012", "name": "隆基绿能"},
    {"symbol": "000651", "prefix": "sz000651", "name": "格力电器"},
]

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def fetch_stock_daily(symbol: str, prefix: str, start_date: str = "20230101", end_date: str = "20260101", adjust: str = "qfq") -> pd.DataFrame:
    """
    获取单只股票前复权日线数据 (支持 Sina 与 EM 接口互备)
    """
    df = pd.DataFrame()
    # 优先方法 1: 新浪接口 stock_zh_a_daily
    try:
        df = ak.stock_zh_a_daily(symbol=prefix, start_date=start_date, end_date=end_date, adjust=adjust)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
    except Exception as e:
        print(f"  (新浪接口暂不可用，尝试东财接口: {e})", flush=True)

    # 备用方法 2: 东财接口 stock_zh_a_hist
    if df.empty:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust=adjust)
        column_mapping = {
            "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
            "收盘": "close", "成交量": "volume", "成交额": "amount"
        }
        df = df.rename(columns=column_mapping)
        df['date'] = pd.to_datetime(df['date'])

    if df.empty:
        raise ValueError(f"无法获取股票 {symbol} 的数据！")

    df['symbol'] = symbol
    required_cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'amount']
    df = df[required_cols].sort_values('date').reset_index(drop=True)
    return df

def fetch_and_save_all(start_date: str = "20230101", end_date: str = "20260101"):
    """
    批量获取 10 只目标股票数据并保存为 Parquet 文件
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    all_dfs = []

    print("🚀 开始抓取 10 只沪深 300 成分股日线数据...\n", flush=True)

    for stock in TARGET_STOCKS:
        sym = stock["symbol"]
        prefix = stock["prefix"]
        name = stock["name"]
        single_path = os.path.join(DATA_DIR, f"{sym}.parquet")

        try:
            print(f"正在抓取 [{name}] ({sym})...", flush=True)
            df = fetch_stock_daily(symbol=sym, prefix=prefix, start_date=start_date, end_date=end_date)
            df['name'] = name
            
            # 保存单只股票 Parquet
            df.to_parquet(single_path, index=False)
            print(f"  ✓ {name}({sym}) 保存成功! 共 {len(df)} 条记录", flush=True)
            
            all_dfs.append(df)
            time.sleep(0.3)
        except Exception as e:
            print(f"  ✗ 获取股票 {name}({sym}) 失败: {e}", flush=True)

    if all_dfs:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        combined_path = os.path.join(DATA_DIR, "stocks_daily.parquet")
        combined_df.to_parquet(combined_path, index=False)
        print(f"\n🎉 汇总数据保存成功: {combined_path} (共 {len(combined_df)} 条记录，涵盖 {len(all_dfs)} 只股票)", flush=True)

if __name__ == "__main__":
    fetch_and_save_all()
