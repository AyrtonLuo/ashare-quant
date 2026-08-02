"""
base.py — Unified Data Provider Abstract Interface & Provider Error definitions.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.contracts.corporate_action import CorporateActionContract


class ProviderError(Exception):
    """Base exception for data provider timeouts, rate limits, and schema changes."""
    def __init__(self, provider_id: str, error_message: str):
        self.provider_id = provider_id
        self.error_message = error_message
        super().__init__(f"[{provider_id}] Provider Error: {error_message}")


class UnifiedDataProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str: pass

    @property
    @abstractmethod
    def provider_version(self) -> str: pass

    @abstractmethod
    def fetch_market_data(self, symbol: str, trade_date: str) -> Optional[MarketDataContract]:
        """Fetches daily bar market data adapted into MarketDataContract."""
        pass

    @abstractmethod
    def fetch_fundamental_data(self, symbol: str, trade_date: str) -> Optional[FundamentalDataContract]:
        """Fetches point-in-time fundamental statement adapted into FundamentalDataContract."""
        pass

    @abstractmethod
    def fetch_corporate_actions(self, symbol: str, start_date: str, end_date: str) -> List[CorporateActionContract]:
        """Fetches corporate action events."""
        pass
