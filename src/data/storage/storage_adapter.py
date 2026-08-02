"""
storage_adapter.py — Historical Data Storage Adapter Interface & Parquet/InMemory Adapters.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any
from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract


class BaseStorageAdapter(ABC):
    @abstractmethod
    def save_market_data(self, dataset_id: str, contracts: List[MarketDataContract]):
        pass

    @abstractmethod
    def load_market_data(self, dataset_id: str, symbol: str) -> List[MarketDataContract]:
        pass


class InMemoryStorageAdapter(BaseStorageAdapter):
    """In-memory storage adapter for fast deterministic testing and Golden Dataset storage."""

    def __init__(self):
        self._market_store: dict = {}

    def save_market_data(self, dataset_id: str, contracts: List[MarketDataContract]):
        if dataset_id not in self._market_store:
            self._market_store[dataset_id] = {}
        for c in contracts:
            if c.symbol not in self._market_store[dataset_id]:
                self._market_store[dataset_id][c.symbol] = []
            self._market_store[dataset_id][c.symbol].append(c)

    def load_market_data(self, dataset_id: str, symbol: str) -> List[MarketDataContract]:
        return self._market_store.get(dataset_id, {}).get(symbol, [])
