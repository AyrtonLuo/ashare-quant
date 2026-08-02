"""
engine.py — Signal Engine emitting research recommendations (-1.0 to +1.0).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List


@dataclass(frozen=True)
class SignalRecommendation:
    symbol: str
    effective_date: str
    factor_name: str
    normalized_score: float
    signal_score: float      # Bound between -1.0 and +1.0
    bias_category: str       # "BUY_BIAS", "NEUTRAL", "SELL_BIAS"


class SignalEngine:
    """Converts normalized factor z-scores into signal recommendations."""

    @staticmethod
    def generate_signals(
        normalized_scores: Dict[str, float], factor_name: str, effective_date: str
    ) -> List[SignalRecommendation]:
        signals = []
        for symbol, z_score in normalized_scores.items():
            # Sigmoid/clipping transform to [-1.0, 1.0]
            sig_val = float(max(-1.0, min(1.0, z_score / 2.0)))
            
            if sig_val > 0.3:
                bias = "BUY_BIAS"
            elif sig_val < -0.3:
                bias = "SELL_BIAS"
            else:
                bias = "NEUTRAL"

            signals.append(
                SignalRecommendation(
                    symbol=symbol,
                    effective_date=effective_date,
                    factor_name=factor_name,
                    normalized_score=z_score,
                    signal_score=sig_val,
                    bias_category=bias
                )
            )
        return signals
