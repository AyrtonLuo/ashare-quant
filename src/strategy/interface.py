"""
interface.py
策略统一抽象接口类 (Strategy)
策略仅感知 Market Data, Portfolio State 和 Timestamp，不直接依赖数据源或执行细节。
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from src.strategy.signal import StrategySignal
from src.data.provider import MarketDataProvider


class Strategy(ABC):
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id

    @abstractmethod
    def generate_signal(
        self,
        data_provider: MarketDataProvider,
        portfolio_state: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ) -> StrategySignal:
        """
        根据数据提供器与当前持仓状态生成 Target Portfolio StrategySignal
        """
        pass
