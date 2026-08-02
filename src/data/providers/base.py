"""
base.py — Abstract Data Provider Interface.
"""

from abc import ABC, abstractmethod
from typing import Optional
from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract


class BaseDataProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: pass

    @abstractmethod
    def fetch_market_data(self, symbol: str, trade_date: str) -> Optional[MarketDataContract]:
        """Fetches and adapts market data into Canonical MarketDataContract."""
        pass

    @abstractmethod
    def fetch_fundamental_data(self, symbol: str, trade_date: str) -> Optional[FundamentalDataContract]:
        """Fetches and adapts fundamental data into Canonical FundamentalDataContract."""
        pass
