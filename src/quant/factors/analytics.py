"""
analytics.py — Factor Exposure, Correlation Matrix & Rank IC Analytics Engine.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np
from scipy.stats import spearmanr, pearsonr


@dataclass(frozen=True)
class RankICResult:
    factor_name: str
    ic_mean: float
    ic_std: float
    icir: float
    positive_ic_ratio: float
    decay_curve: Dict[int, float]  # {1: 0.05, 5: 0.04, 10: 0.03, 20: 0.02, 60: 0.01}


class FactorAnalytics:
    """Computes Factor Exposure, Pearson Correlation Matrix, and Rank IC / ICIR / Decay."""

    @staticmethod
    def calculate_factor_exposure(
        portfolio_weights: Dict[str, float], factor_scores: Dict[str, float]
    ) -> float:
        """Calculates portfolio weighted factor exposure."""
        exposure = 0.0
        for sym, w in portfolio_weights.items():
            if sym in factor_scores:
                exposure += w * factor_scores[sym]
        return round(exposure, 4)

    @staticmethod
    def calculate_correlation_matrix(
        factor_scores_dict: Dict[str, Dict[str, float]]
    ) -> Dict[Tuple[str, str], float]:
        """Calculates Pearson Correlation Matrix across pairs of factors."""
        f_names = list(factor_scores_dict.keys())
        correlations: Dict[Tuple[str, str], float] = {}

        for i in range(len(f_names)):
            for j in range(i, len(f_names)):
                f1, f2 = f_names[i], f_names[j]
                common_symbols = set(factor_scores_dict[f1].keys()) & set(factor_scores_dict[f2].keys())
                
                if len(common_symbols) < 3:
                    correlations[(f1, f2)] = 0.0
                    continue

                arr1 = np.array([factor_scores_dict[f1][s] for s in common_symbols])
                arr2 = np.array([factor_scores_dict[f2][s] for s in common_symbols])
                
                corr = float(np.corrcoef(arr1, arr2)[0, 1]) if np.std(arr1) > 0 and np.std(arr2) > 0 else 0.0
                correlations[(f1, f2)] = round(corr, 4)
                correlations[(f2, f1)] = round(corr, 4)

        return correlations

    @staticmethod
    def calculate_rank_ic(
        factor_scores: Dict[str, float], future_returns: Dict[str, float]
    ) -> float:
        """Calculates Spearman Rank IC between Factor Scores and Future Returns."""
        common = set(factor_scores.keys()) & set(future_returns.keys())
        if len(common) < 3:
            return 0.0

        f_vals = [factor_scores[s] for s in common]
        r_vals = [future_returns[s] for s in common]
        
        ic, _ = spearmanr(f_vals, r_vals)
        return float(round(ic, 4)) if not np.isnan(ic) else 0.0

    @staticmethod
    def calculate_ic_decay(
        factor_scores: Dict[str, float], multi_period_returns: Dict[int, Dict[str, float]]
    ) -> Dict[int, float]:
        """Calculates Rank IC decay across 1D, 5D, 10D, 20D, 60D forward return horizons."""
        decay = {}
        for horizon, ret_dict in multi_period_returns.items():
            decay[horizon] = FactorAnalytics.calculate_rank_ic(factor_scores, ret_dict)
        return decay
