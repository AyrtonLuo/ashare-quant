"""
simple_momentum.py — Simple Momentum Quantitative Strategy.
"""

from typing import List, Dict
from src.quant.strategies.base import BaseStrategy
from src.quant.signals.engine import SignalRecommendation


class SimpleMomentumStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "simple_momentum_strategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    def generate_target_portfolio(
        self, signals: List[SignalRecommendation], top_n: int = 5
    ) -> Dict[str, float]:
        # Filter BUY_BIAS signals
        candidates = [s for s in signals if s.signal_score > 0]
        sorted_candidates = sorted(candidates, key=lambda s: s.signal_score, reverse=True)
        
        selected = sorted_candidates[:top_n]
        if not selected:
            return {}

        weight = round(1.0 / len(selected), 4)
        return {s.symbol: weight for s in selected}
