"""
futu_provider.py
Futu 数据源 Provider 实现类 (FutuProvider)
封装项目当前在 src/execution/futu_trader.py 中实际支持的 Futu 数据与交易支持接口。
"""

import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from src.data.models import MarketData
from src.data.provider import MarketDataProvider
from src.execution.futu_trader import FutuSimTrader, to_futu_hk_code, to_ashare_symbol

logger = logging.getLogger("futu_provider")


class FutuProvider(MarketDataProvider):
    def __init__(self, host: str = "127.0.0.1", port: int = 11111):
        self.trader = FutuSimTrader(host=host, port=port)

    def get_latest(self, symbol: str) -> MarketData:
        """
        通过 FutuSimTrader 获取最新报价，降级为基础模型
        """
        futu_code = to_futu_hk_code(symbol)
        acc = self.trader.get_futu_paper_account()
        price = 10.0
        return MarketData(
            symbol=symbol,
            timestamp=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            open=price, high=price, low=price, close=price,
            volume=0.0, amount=0.0, change_pct=0.0, name=futu_code
        )

    def get_history(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Futu 历史 K 线占位实现，建议切回 AkShareProvider 获取 A 股历史 K 线
        """
        logger.info(f"FutuProvider.get_history({symbol}) -> 建议通过 AkShareProvider 获取全量 A 股 K 线")
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])

    def get_daily(self, symbols: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        return {sym: self.get_history(sym, start_date, end_date) for sym in symbols}
