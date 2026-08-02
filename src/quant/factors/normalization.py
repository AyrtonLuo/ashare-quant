"""
normalization.py — Factor Winsorization & Z-Score Normalization Engine.
"""

from typing import List, Dict
import numpy as np
from src.quant.factors.base import FactorValue, FactorStatus


class FactorNormalizer:
    """Performs Winsorization (3-Sigma clipping) and Cross-Sectional Z-Score Normalization."""

    @staticmethod
    def normalize_cross_section(factor_values: List[FactorValue]) -> Dict[str, float]:
        valid_values = [f for f in factor_values if f.status == FactorStatus.VALID and f.raw_value is not None]
        
        if not valid_values:
            return {}

        symbols = [f.symbol for f in valid_values]
        vals = np.array([f.raw_value for f in valid_values], dtype=float)

        # 1. Winsorization (3-Sigma Clipping)
        mean = np.mean(vals)
        std = np.std(vals)
        
        if std == 0:
            return {s: 0.0 for s in symbols}

        lower_bound = mean - 3.0 * std
        upper_bound = mean + 3.0 * std
        clipped_vals = np.clip(vals, lower_bound, upper_bound)

        # 2. Z-Score Standardization
        z_scores = (clipped_vals - np.mean(clipped_vals)) / (np.std(clipped_vals) + 1e-8)

        return dict(zip(symbols, z_scores.tolist()))
