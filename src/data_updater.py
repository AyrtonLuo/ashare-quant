"""
data_updater.py
增量数据更新管道：自动读取本地 Parquet 数据缓存的最大日期，通过 akshare 增量抓取新交易日数据，
去重并正序排列后完成合并更新。
"""

import os
import sys
import time
import logging
import pandas as pd
import akshare as ak
from datetime import datetime

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data_fetch import TARGET_STOCKS, fetch_stock_daily

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# 日志模块配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("data_updater")


def update_incremental_stock_data(end_date: str = None) -> bool:
    """
    检查并增量更新本地 Parquet 股票数据
    
    参数:
        end_date: 抓取目标截止日期 (默认今天 YYYYMMDD)
        
    返回:
        bool: 是否更新了新数据
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")

    os.makedirs(DATA_DIR, exist_ok=True)
    all_dfs = []
    updated_count = 0

    logger.info("开始检验本地数据缓存并执行增量更新检测...")

    for stock in TARGET_STOCKS:
        sym = stock["symbol"]
        prefix = stock["prefix"]
        name = stock["name"]
        single_path = os.path.join(DATA_DIR, f"{sym}.parquet")

        if os.path.exists(single_path):
            try:
                old_df = pd.read_parquet(single_path)
                old_df['date'] = pd.to_datetime(old_df['date'])
                
                # 获取本地最大的已有交易日
                latest_date_dt = old_df['date'].max()
                latest_date_str = latest_date_dt.strftime("%Y%m%d")
                
                # 若已有数据已是最新，跳过重复请求
                if latest_date_str >= end_date:
                    logger.info(f"[{name}]({sym}) 已是最新数据 ({latest_date_str})，跳过增量更新。")
                    all_dfs.append(old_df)
                    continue

                # 仅从最新日期的下一天起开始增量抓取
                fetch_start = latest_date_dt.strftime("%Y%m%d")
                logger.info(f"[{name}]({sym}) 本地最大日期: {latest_date_str}，开始从 {fetch_start} 抓取增量数据...")
                
                new_df = fetch_stock_daily(symbol=sym, prefix=prefix, start_date=fetch_start, end_date=end_date)
                new_df['name'] = name
                
                # 合并新旧数据
                combined_df = pd.concat([old_df, new_df], ignore_index=True)
                
                # =========================================================================
                # 🚨 【工程规范】：1. 去重按 date ; 2. 必须正序排列 sort_values('date')
                # =========================================================================
                combined_df = combined_df.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
                
                combined_df.to_parquet(single_path, index=False)
                new_rows = len(combined_df) - len(old_df)
                logger.info(f"  ✓ [{name}]({sym}) 成功更新 {new_rows} 条新数据，最新纪录共 {len(combined_df)} 条。")
                
                all_dfs.append(combined_df)
                updated_count += 1
                time.sleep(0.3)
                continue
                
            except Exception as e:
                logger.warning(f"增量更新股票 [{name}]({sym}) 出现异常 ({e})，保留原有本地数据。")
                if os.path.exists(single_path):
                    all_dfs.append(pd.read_parquet(single_path))
        else:
            # 文件不存在，全量抓取
            try:
                logger.info(f"本地缺少 [{name}]({sym}) 缓存，开始全量抓取...")
                df = fetch_stock_daily(symbol=sym, prefix=prefix, start_date="20230101", end_date=end_date)
                df['name'] = name
                df = df.sort_values('date').reset_index(drop=True)
                df.to_parquet(single_path, index=False)
                all_dfs.append(df)
                updated_count += 1
            except Exception as e:
                logger.error(f"全量抓取股票 [{name}]({sym}) 失败: {e}")

    if all_dfs:
        combined_all = pd.concat(all_dfs, ignore_index=True)
        # 严格按 [symbol, date] 去重并按 date 正序排列
        combined_all = combined_all.drop_duplicates(subset=['symbol', 'date']).sort_values(['symbol', 'date']).reset_index(drop=True)
        
        combined_path = os.path.join(DATA_DIR, "stocks_daily.parquet")
        combined_all.to_parquet(combined_path, index=False)
        logger.info(f"🎉 本地汇总数据更新完成: {combined_path} (涵盖 {len(all_dfs)} 只股票，共 {len(combined_all)} 条记录)。")

    return updated_count > 0

if __name__ == "__main__":
    update_incremental_stock_data()
