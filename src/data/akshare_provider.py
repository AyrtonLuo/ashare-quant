"""
akshare_provider.py
AkShare 数据源 Provider 实现类 (AkShareProvider)
实现 MarketDataProvider 接口，集成 LocalCache，严格包含数据血缘信息。
当真实 API 与 LocalCache 均不可用时，强断言返回 status="DATA_UNAVAILABLE" 状态对象，绝对不生成假价格。
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
        获取单只股票或指数的最新报价，封装为统一 MarketData 对象。
        当 API 异常时强抛置为 status="DATA_UNAVAILABLE"，不伪造价格。
        """
        info = normalize_ashare_code(symbol)
        suffix = info["suffix"]
        code6 = info["code6"]
        name = info.get("name", suffix)

        try:
            spot = get_single_stock_spot(suffix if info["is_index"] else code6)
            price = spot.get("price")
            status = spot.get("status", "AVAILABLE" if price is not None else "DATA_UNAVAILABLE")
            if status == "AVAILABLE" and price is not None:
                p_val = float(price)
                return MarketData(
                    symbol=suffix,
                    timestamp=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                    open=float(spot.get("open", p_val)),
                    high=float(spot.get("high", p_val)),
                    low=float(spot.get("low", p_val)),
                    close=p_val,
                    volume=float(spot.get("volume", 0.0)),
                    amount=float(spot.get("amount", 0.0)),
                    change_pct=float(spot.get("change_pct", 0.0)),
                    name=str(spot.get("name", name)),
                    source=str(spot.get("source", "AkShare Realtime API")),
                    data_mode="RESEARCH",
                    is_real=True,
                    status="AVAILABLE"
                )
        except Exception as e:
            logger.warning(f"AkShareProvider.get_latest({suffix}) 异常 ({e})，标记 DATA_UNAVAILABLE")

        return MarketData(
            symbol=suffix,
            timestamp=None,
            open=None,
            high=None,
            low=None,
            close=None,
            volume=0.0,
            amount=0.0,
            change_pct=0.0,
            name=name,
            source=None,
            data_mode="RESEARCH",
            is_real=False,
            status="DATA_UNAVAILABLE"
        )

    def get_history(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None, force_refresh: bool = False) -> pd.DataFrame:
        """
        获取单只股票/指数前复权历史 K 线 DataFrame
        优先查本地 Exchange 隔离缓存，若无或强制刷线则调取 AkShare 接口并自动落盘
        """
        info = normalize_ashare_code(symbol)
        suffix = info["suffix"]
        code6 = info["code6"]

        if self.use_cache and not force_refresh:
            cached_df = self.cache.load(suffix)
            if cached_df is not None and not cached_df.empty:
                df = cached_df.copy()
                df['date'] = pd.to_datetime(df['date'])
                if start_date:
                    df = df[df['date'] >= pd.to_datetime(start_date)]
                if end_date:
                    df = df[df['date'] <= pd.to_datetime(end_date)]
                return df

        df = fetch_historical_kline(code6, period="daily", adjust="qfq")
        if df is not None and not df.empty:
            if self.use_cache:
                self.cache.save(suffix, df)
            df['date'] = pd.to_datetime(df['date'])
            if start_date:
                df = df[df['date'] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df['date'] <= pd.to_datetime(end_date)]
            return df

        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])

    def get_daily(self, symbols: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        result = {}
        for sym in symbols:
            result[sym] = self.get_history(sym, start_date=start_date, end_date=end_date)
        return result
