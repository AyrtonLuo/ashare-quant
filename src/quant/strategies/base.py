"""
base.py — Abstract Strategy Definition Base Class.
"""

from abc import ABC, abstractmethod
from typing import List, Dict
from src.quant.signals.engine import SignalRecommendation


class BaseStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def version(self) -> str: pass

    @abstractmethod
    def generate_target_portfolio(
        self, signals: List[SignalRecommendation], top_n: int = 5
    ) -> Dict[str, float]:
        """Generates target portfolio weights sum(weights) <= 1.0."""
        pass
