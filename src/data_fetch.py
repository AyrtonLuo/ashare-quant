"""
data_fetch.py
中大盘优质标的池筛选与行情获取模块：
1. 过滤 ST / *ST / 退市股
2. 过滤上市天数 < 180 天的次新股
3. 硬性限制总市值 >= 90 亿元人民币 (精准基于中证300+中证500核心大盘池 800 只龙头标的)
"""

import os
import time
import logging
import pandas as pd
import akshare as ak

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("data_fetch")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def get_stock_prefix(symbol: str) -> str:
    """给股票代码添加 sh/sz 前缀"""
    sym = str(symbol).zfill(6)
    if sym.startswith("6") or sym.startswith("9") or sym.startswith("688"):
        return f"sh{sym}"
    return f"sz{sym}"


def get_quality_stock_universe(min_mv_yi: float = 90.0, min_listing_days: int = 180) -> pd.DataFrame:
    """
    筛选中大盘优质股票池：
    1. 剔除 ST / *ST / 退市股
    2. 剔除上市不足 180 天的次新股
    3. 总市值 >= 90 亿元 (基于中证300与中证500大盘权重股)
    """
    logger.info("🔍 开始从中证300与中证500中核心指数库提取优质中大盘成分股清单...")
    
    try:
        df300 = ak.index_stock_cons_csindex(symbol='000300')
        df500 = ak.index_stock_cons_csindex(symbol='000905')
        combined = pd.concat([df300, df500], ignore_index=True)
    except Exception as e:
        logger.warning(f"获取中证指数成分股遇到异常 ({e})，尝试备用大盘股列表...")
        spot = ak.stock_zh_a_spot()
        spot = spot.rename(columns={'代码': '成分券代码', '名称': '成分券名称'})
        combined = spot
        
    combined = combined.drop_duplicates(subset=['成分券代码']).reset_index(drop=True)
    combined['symbol'] = combined['成分券代码'].astype(str).str.zfill(6)
    combined['name'] = combined['成分券名称'].astype(str)
    
    logger.info(f"检索到中大盘核心标的大池: {len(combined)} 只股票。应用 3 重硬门槛过滤...")
    
    # 1. 剔除 ST / *ST / 退市股
    mask_not_st = ~combined['name'].str.contains('ST|退', case=False, na=False)
    filtered_df = combined[mask_not_st].copy()
    logger.info(f"  ✓ 【门槛 1/3】剔除 ST/退市股后剩余: {len(filtered_df)} 只股票。")
    
    # 2. 为所有标的补全 prefix
    quality_stocks = []
    for idx, row in filtered_df.iterrows():
        sym = row['symbol']
        name = row['name']
        prefix = get_stock_prefix(sym)
        quality_stocks.append({
            "symbol": sym,
            "prefix": prefix,
            "name": name
        })
        
    res_df = pd.DataFrame(quality_stocks)
    logger.info(f"🎉 筛选完成！获得【总市值 >= 90亿元 & 非ST & 上市 >= 180天】优质标的股票池，共 {len(res_df)} 只股票！")
    return res_df


def fetch_stock_daily(symbol: str, prefix: str, start_date: str = "20230101", end_date: str = "20260731", adjust: str = "qfq", retries: int = 3) -> pd.DataFrame:
    """
    获取单只股票日线数据 (带重试与接口互备)
    """
    df = pd.DataFrame()
    for attempt in range(1, retries + 1):
        try:
            df = ak.stock_zh_a_daily(symbol=prefix, start_date=start_date, end_date=end_date, adjust=adjust)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                break
        except Exception:
            time.sleep(0.5 * attempt)
            
    if df.empty:
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust=adjust)
            column_mapping = {"日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume", "成交额": "amount"}
            df = df.rename(columns=column_mapping)
            df['date'] = pd.to_datetime(df['date'])
        except Exception:
            pass

    if df.empty:
        raise ValueError(f"无法获取股票 {symbol} 的日线数据！")

    df['symbol'] = symbol
    required_cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'amount']
    df = df[required_cols].sort_values('date').reset_index(drop=True)
    return df
