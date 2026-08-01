"""
demo_provider.py
Product Demo Mode 确定性演示数据源 (DemoMarketDataProvider)
解耦外部 API 与网络依赖，保证演练模式下功能完好体验。
声明 data_mode="DEMO", is_real=False，严格与 RESEARCH MODE 隔离。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from src.data.models import MarketData
from src.data.provider import MarketDataProvider
from src.data.symbol_utils import normalize_ashare_code


class DemoMarketDataProvider(MarketDataProvider):
    def __init__(self):
        pass

    def get_latest(self, symbol: str) -> MarketData:
        info = normalize_ashare_code(symbol)
        suffix = info["suffix"]
        code6 = info["code6"]

        prices = {
            "000001.SH": 3280.50,
            "000001.SZ": 11.63,
            "399001.SZ": 10450.20,
            "399006.SZ": 2180.10,
            "000300.SH": 3890.40,
            "000852.SH": 5600.30,
            "600519.SH": 1450.00
        }
        price = prices.get(suffix, prices.get(code6, 100.0))
        return MarketData(
            symbol=suffix,
            timestamp=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            open=price * 0.995,
            high=price * 1.01,
            low=price * 0.99,
            close=price,
            volume=50000.0,
            amount=5000000.0,
            change_pct=0.82,
            name=f"Demo_{info['name']}",
            source="DemoMarketDataProvider",
            data_mode="DEMO",
            is_real=False,
            status="AVAILABLE"
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
