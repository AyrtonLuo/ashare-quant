"""
cache.py
本地数据缓存模块 (LocalCache) 包含严格 Exchange / Namespace 隔离
自动按 data/indices/000001.SH.parquet 与 data/stocks/000001.SZ.parquet 分别存储。
拒绝对裸代码 '000001.parquet' 进行模糊猜测，防止数据污染。
"""

import os
import logging
import pandas as pd
from typing import Optional
from src.data.symbol_utils import normalize_ashare_code

logger = logging.getLogger("cache")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")


class LocalCache:
    def __init__(self, cache_dir: str = DATA_DIR):
        self.cache_dir = cache_dir
        self.indices_dir = os.path.join(self.cache_dir, "indices")
        self.stocks_dir = os.path.join(self.cache_dir, "stocks")
        os.makedirs(self.indices_dir, exist_ok=True)
        os.makedirs(self.stocks_dir, exist_ok=True)

    def get_symbol_path(self, symbol: str) -> str:
        info = normalize_ashare_code(symbol)
        suffix = info["suffix"]
        is_index = info["is_index"]

        target_dir = self.indices_dir if is_index else self.stocks_dir
        return os.path.join(target_dir, f"{suffix}.parquet")

    def exists(self, symbol: str) -> bool:
        path = self.get_symbol_path(symbol)
        if os.path.exists(path):
            return True
        # 兼容已有旧文件路径如 data/stocks/600519.parquet
        info = normalize_ashare_code(symbol)
        code6 = info["code6"]
        if code6 != "000001":
            old_path = os.path.join(self.stocks_dir, f"{code6}.parquet")
            old_root = os.path.join(self.cache_dir, f"{code6}.parquet")
            return os.path.exists(old_path) or os.path.exists(old_root)
        return False

    def load(self, symbol: str) -> Optional[pd.DataFrame]:
        path = self.get_symbol_path(symbol)
        if os.path.exists(path):
            try:
                df = pd.read_parquet(path)
                if not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"读取缓存 {path} 异常 ({e})")

        # 降级尝试已有旧文件路径 (000001 除外，绝对不猜测)
        info = normalize_ashare_code(symbol)
        code6 = info["code6"]
        if code6 != "000001":
            for p in [os.path.join(self.stocks_dir, f"{code6}.parquet"), os.path.join(self.cache_dir, f"{code6}.parquet")]:
                if os.path.exists(p):
                    try:
                        df = pd.read_parquet(p)
                        if not df.empty:
                            return df
                    except Exception:
                        pass
        return None

    def save(self, symbol: str, df: pd.DataFrame):
        if df is None or df.empty:
            return
        path = self.get_symbol_path(symbol)
        try:
            df.to_parquet(path, index=False)
        except Exception as e:
            logger.error(f"写入缓存 {path} 异常 ({e})")
