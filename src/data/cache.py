"""
cache.py
本地数据缓存模块 (LocalCache)
支持优先读取本地 Parquet 缓存，避免重复触发网络拉取拖慢系统线速度。
"""

import os
import logging
import pandas as pd
from typing import Optional

logger = logging.getLogger("cache")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")


class LocalCache:
    def __init__(self, cache_dir: str = DATA_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_symbol_path(self, symbol: str) -> str:
        code6 = str(symbol).zfill(6)
        return os.path.join(self.cache_dir, f"{code6}.parquet")

    def exists(self, symbol: str) -> bool:
        return os.path.exists(self.get_symbol_path(symbol))

    def load(self, symbol: str) -> Optional[pd.DataFrame]:
        path = self.get_symbol_path(symbol)
        if os.path.exists(path):
            try:
                df = pd.read_parquet(path)
                if not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"读取缓存 {path} 异常 ({e})")
        return None

    def save(self, symbol: str, df: pd.DataFrame):
        if df is None or df.empty:
            return
        path = self.get_symbol_path(symbol)
        try:
            df.to_parquet(path, index=False)
        except Exception as e:
            logger.error(f"写入缓存 {path} 异常 ({e})")
