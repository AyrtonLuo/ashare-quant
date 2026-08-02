"""
multi_factor.py — Multi-Factor Engine combining Momentum, Volatility, Liquidity, Value factors.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from src.quant.factors.base import FactorValue, FactorStatus


class FactorDirection(str, Enum):
    POSITIVE = "POSITIVE"  # Higher score = Preferred (e.g. Momentum)
    NEGATIVE = "NEGATIVE"  # Lower score = Preferred (e.g. PE, Volatility)


@dataclass(frozen=True)
class FactorWeightConfig:
    factor_name: str
    weight: float
    direction: FactorDirection


class MultiFactorEngine:
    """Combines multiple factor Z-Scores into a Composite Factor Score."""

    def __init__(self, factor_configs: List[FactorWeightConfig]):
        self.factor_configs = factor_configs
        # Normalize weights so sum = 1.0
        total_w = sum(abs(cfg.weight) for cfg in factor_configs) or 1.0
        self.normalized_configs = [
            FactorWeightConfig(cfg.factor_name, cfg.weight / total_w, cfg.direction)
            for cfg in factor_configs
        ]

    def compute_composite_scores(
        self, factor_matrices: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """
        factor_matrices: Dict[factor_name, Dict[symbol, normalized_z_score]]
        Returns: Dict[symbol, composite_factor_score]
        """
        all_symbols = set()
        for f_name, sym_scores in factor_matrices.items():
            all_symbols.update(sym_scores.keys())

        composite_scores: Dict[str, float] = {}

        for symbol in all_symbols:
            score_sum = 0.0
            valid_factor_count = 0

            for cfg in self.normalized_configs:
                f_name = cfg.factor_name
                if f_name in factor_matrices and symbol in factor_matrices[f_name]:
                    val = factor_matrices[f_name][symbol]
                    # Invert direction if NEGATIVE factor (e.g. lower volatility = higher composite score)
                    adj_val = val if cfg.direction == FactorDirection.POSITIVE else -val
                    score_sum += adj_val * cfg.weight
                    valid_factor_count += 1

            if valid_factor_count > 0:
                composite_scores[symbol] = round(score_sum, 4)

        return composite_scores
