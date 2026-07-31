"""
data_updater.py
多线程并发增量数据更新管道：
使用 ThreadPoolExecutor 对 90 亿+ 市值优质股票池进行并发抓取，
包含指数退避重试 (Exponential Backoff)、断点续传、正序排列 (sort_values('date')) 与日志记录。
"""

import os
import sys
import time
import random
import logging
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data_fetch import get_quality_stock_universe, fetch_stock_daily, get_stock_prefix

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STOCKS_DIR = os.path.join(DATA_DIR, "stocks")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("data_updater")


def process_single_stock_download(stock_info: dict, end_date: str = "20260731", max_retries: int = 4) -> tuple[str, pd.DataFrame, int]:
    """
    单只股票抓取 worker 函数（含指数退避重试与断点续传）
    """
    sym = stock_info["symbol"]
    prefix = stock_info.get("prefix", get_stock_prefix(sym))
    name = stock_info["name"]
    single_path = os.path.join(STOCKS_DIR, f"{sym}.parquet")

    old_df = pd.DataFrame()
    fetch_start = "20130101"

    if os.path.exists(single_path):
        try:
            old_df = pd.read_parquet(single_path)
            old_df['date'] = pd.to_datetime(old_df['date'])
            latest_date_dt = old_df['date'].max()
            latest_date_str = latest_date_dt.strftime("%Y%m%d")
            
            if latest_date_str >= end_date:
                return sym, old_df, 0
            fetch_start = latest_date_str
        except Exception:
            old_df = pd.DataFrame()

    # 指数退避重试循环
    new_df = pd.DataFrame()
    for attempt in range(1, max_retries + 1):
        try:
            new_df = fetch_stock_daily(symbol=sym, prefix=prefix, start_date=fetch_start, end_date=end_date)
            new_df['name'] = name
            break
        except Exception as e:
            if attempt == max_retries:
                logger.warning(f"  ✗ [{name}]({sym}) 重试 {max_retries} 次仍失败，保留原有数据。")
            else:
                # 指数退避延迟 + 随机抖动 (Exponential Backoff with Jitter)
                delay = (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                time.sleep(delay)

    if not new_df.empty:
        if not old_df.empty:
            combined_df = pd.concat([old_df, new_df], ignore_index=True)
        else:
            combined_df = new_df
            
        # =========================================================================
        # 🚨 【工程规范】：1. 按 date 去重 ; 2. 必须正序排列 sort_values('date')
        # =========================================================================
        combined_df = combined_df.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
        combined_df.to_parquet(single_path, index=False)
        new_added = len(combined_df) - len(old_df)
        return sym, combined_df, new_added

    return sym, old_df, 0


def update_quality_universe_data(max_workers: int = 8, end_date: str = "20260731") -> pd.DataFrame:
    """
    多线程并发抓取 90 亿+ 市值股票池日线数据
    """
    os.makedirs(STOCKS_DIR, exist_ok=True)
    
    # 1. 筛选优质股票池
    universe_df = get_quality_stock_universe(min_mv_yi=90.0, min_listing_days=180)
    stock_list = universe_df.to_dict('records')
    total_stocks = len(stock_list)
    
    logger.info(f"🚀 开始使用 ThreadPoolExecutor ({max_workers} 线程并发) 抓取 {total_stocks} 只 90亿+ 市值标的日线数据...\n")
    
    all_dfs = []
    completed_count = 0
    total_new_rows = 0

    # 2. 多线程并发调度
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_stock = {
            executor.submit(process_single_stock_download, stock, end_date): stock
            for stock in stock_list
        }
        
        for future in as_completed(future_to_stock):
            stock = future_to_stock[future]
            completed_count += 1
            try:
                sym, df, new_rows = future.result()
                if not df.empty:
                    all_dfs.append(df)
                    total_new_rows += new_rows
                if completed_count % 10 == 0 or completed_count == total_stocks:
                    logger.info(f"进度: [{completed_count}/{total_stocks}] (已完成 {completed_count/total_stocks*100:.1f}%)")
            except Exception as exc:
                logger.error(f"股票 {stock['name']}({stock['symbol']}) 线程处理抛出异常: {exc}")

    if all_dfs:
        combined_all = pd.concat(all_dfs, ignore_index=True)
        # 严格按 [symbol, date] 去重并按 date 正序排列
        combined_all = combined_all.drop_duplicates(subset=['symbol', 'date']).sort_values(['symbol', 'date']).reset_index(drop=True)
        
        combined_path = os.path.join(DATA_DIR, "stocks_daily.parquet")
        combined_all.to_parquet(combined_path, index=False)
        logger.info(f"\n🎉 90亿+ 市值全标的数据并发更新完成！汇总文件: {combined_path} (涵盖 {len(all_dfs)} 只股票，共 {len(combined_all)} 条记录)。")
        return combined_all
    else:
        raise RuntimeError("未成功获取到任何股票数据！")


def query_history_with_duckdb(parquet_path: str, start_date: str = "2013-01-01") -> pd.DataFrame:
    """
    针对 2013 至今跨 13 年海量 Parquet 数据的 DuckDB 懒加载 (Lazy Scanning) 查询
    避免一次性载入挤爆内存
    """
    if not os.path.exists(parquet_path):
        raise FileNotFoundError(f"Parquet 数据文件不存在: {parquet_path}")

    try:
        import duckdb
        conn = duckdb.connect(database=':memory:')
        query = f"SELECT * FROM read_parquet('{parquet_path}') WHERE date >= '{start_date}' ORDER BY date, symbol"
        return conn.execute(query).fetchdf()
    except Exception:
        df = pd.read_parquet(parquet_path)
        df['date'] = pd.to_datetime(df['date'])
        return df[df['date'] >= pd.to_datetime(start_date)].sort_values(['date', 'symbol']).reset_index(drop=True)


if __name__ == "__main__":
    update_quality_universe_data()
