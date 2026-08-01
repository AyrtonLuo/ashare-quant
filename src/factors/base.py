"""
base.py
因子统一抽象基类 (Factor)
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, List, Optional
from src.data.provider import MarketDataProvider


class Factor(ABC):
    def __init__(self, name: str, category: str = "general"):
        self.name = name
        self.category = category

    @abstractmethod
    def compute(self, symbol: str, data_provider: MarketDataProvider, cutoff_date: Optional[str] = None) -> float:
        """
        计算单个标的截至 cutoff_date 的因子原始分值 (Raw Factor Score)
        必须使用历史数据，严格防未来函数
        """
        pass
