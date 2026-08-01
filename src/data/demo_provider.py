"""
demo_provider.py
Product Demo Mode 确定性演示数据源 (DemoMarketDataProvider)
解耦外部 API 与网络依赖，保证公网与无网络环境下 100% 功能完好可体验。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from src.data.models import MarketData
from src.data.provider import MarketDataProvider


class DemoMarketDataProvider(MarketDataProvider):
    def __init__(self):
        pass

    def get_latest(self, symbol: str) -> MarketData:
        prices = {
            "000001": 3280.50,
            "399001": 10450.20,
            "399006": 2180.10,
            "000300": 3890.40,
            "000852": 5600.30,
            "600519": 1450.00
        }
        price = prices.get(symbol, 100.0)
        return MarketData(
            symbol=symbol,
            timestamp=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            open=price * 0.995,
            high=price * 1.01,
            low=price * 0.99,
            close=price,
            volume=50000.0,
            amount=5000000.0,
            change_pct=0.82,
            name=f"Demo_{symbol}"
        )

    def get_history(
        self,
        symbol: str,
        start_date: str = "2023-01-01",
        end_date: str = "2026-07-20",
        force_refresh: bool = False
    ) -> pd.DataFrame:
        dates = pd.date_range("2023-01-01", "2026-07-20", freq="B")
        n = len(dates)
        np.random.seed(42)
        returns = np.random.normal(0.0005, 0.015, size=n)
        prices = 100.0 * np.exp(np.cumsum(returns))

        df = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "open": prices * 0.995,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.randint(1000, 10000, size=n) * 100.0
        })
        return df

    def get_daily(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        res = {}
        for sym in symbols:
            res[sym] = self.get_history(sym, start_date=start_date, end_date=end_date)
        return res

