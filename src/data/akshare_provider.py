"""
akshare_provider.py
AkShare 数据源 Provider 实现类 (AkShareProvider)
实现 MarketDataProvider 接口，且集成 LocalCache 进行缓存层调度。
"""

import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from src.data.models import MarketData
from src.data.provider import MarketDataProvider
from src.data.cache import LocalCache
from src.data.symbol_utils import normalize_ashare_code
from src.data.akshare_engine import get_single_stock_spot, fetch_historical_kline

logger = logging.getLogger("akshare_provider")


class AkShareProvider(MarketDataProvider):
    def __init__(self, cache: Optional[LocalCache] = None, use_cache: bool = True):
        self.cache = cache or LocalCache()
        self.use_cache = use_cache

    def get_latest(self, symbol: str) -> MarketData:
        """
        获取单只股票的最新报价，封装为统一 MarketData 对象
        """
        info = normalize_ashare_code(symbol)
        code6 = info["code6"]

        try:
            spot = get_single_stock_spot(code6)
            price = float(spot.get("price", 10.0))
            return MarketData(
                symbol=code6,
                timestamp=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                open=float(spot.get("open", price)),
                high=float(spot.get("high", price)),
                low=float(spot.get("low", price)),
                close=price,
                volume=float(spot.get("volume", 0.0)),
                amount=float(spot.get("amount", 0.0)),
                change_pct=float(spot.get("change_pct", 0.0)),
                name=str(spot.get("name", code6))
            )
        except Exception as e:
            logger.warning(f"AkShareProvider.get_latest({code6}) 异常 ({e})，返回降级报价")
            return MarketData(
                symbol=code6,
                timestamp=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                open=10.0, high=10.0, low=10.0, close=10.0,
                volume=0.0, amount=0.0, change_pct=0.0, name=code6
            )

    def get_history(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None, force_refresh: bool = False) -> pd.DataFrame:
        """
        获取单只股票前复权历史 K 线 DataFrame
        优先查本地缓存，若无或强制刷线则调取 AkShare 接口并自动落盘
        """
        info = normalize_ashare_code(symbol)
        code6 = info["code6"]

        if self.use_cache and not force_refresh:
            cached_df = self.cache.load(code6)
            if cached_df is not None and not cached_df.empty:
                df = cached_df.copy()
                if start_date:
                    df = df[df['date'] >= pd.to_datetime(start_date)]
                if end_date:
                    df = df[df['date'] <= pd.to_datetime(end_date)]
                return df

        df = fetch_historical_kline(code6, period="daily", adjust="qfq")
        if df is not None and not df.empty:
            if self.use_cache:
                self.cache.save(code6, df)
            if start_date:
                df = df[df['date'] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df['date'] <= pd.to_datetime(end_date)]
            return df

        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])

    def get_daily(self, symbols: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """
        批量获取多只股票历史日线
        """
        result = {}
        for sym in symbols:
            result[sym] = self.get_history(sym, start_date=start_date, end_date=end_date)
        return result
