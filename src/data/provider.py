"""
provider.py
行情数据 Provider 统一抽象接口 (MarketDataProvider)
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, List, Optional
from src.data.models import MarketData


class MarketDataProvider(ABC):

    @abstractmethod
    def get_latest(self, symbol: str) -> MarketData:
        """获取最新实时快照报价"""
        pass

    @abstractmethod
    def get_history(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """获取前复权历史 K 线数据"""
        pass

    @abstractmethod
    def get_daily(self, symbols: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """批量获取多只股票日线"""
        pass
