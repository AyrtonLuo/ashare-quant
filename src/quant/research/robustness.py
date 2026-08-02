"""
robustness.py — Robustness Testing Engine: Parameter Sweeps, Out-of-Sample Split & Overfitting Warnings.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Tuple
import numpy as np


@dataclass(frozen=True)
class ParameterSweepResult:
    parameter_grid: List[Dict[str, Any]]
    sharpe_scores: List[float]
    parameter_sensitivity_std: float
    is_highly_sensitive: bool


class RobustnessEngine:
    """Performs bounded Parameter Grid Sweeps, Train/Val/Test Splits, and Overfitting Warning Generation."""

    @staticmethod
    def split_time_series(
        trading_days: List[str], train_pct: float = 0.6, val_pct: float = 0.2
    ) -> Tuple[List[str], List[str], List[str]]:
        """Splits time-series chronologically into Train / Validation / Test sets without shuffling."""
        n = len(trading_days)
        n_train = int(n * train_pct)
        n_val = int(n * val_pct)

        train_days = trading_days[:n_train]
        val_days = trading_days[n_train : n_train + n_val]
        test_days = trading_days[n_train + n_val :]

        return train_days, val_days, test_days

    @staticmethod
    def evaluate_parameter_sweep(
        param_grid: List[Dict[str, Any]], sharpe_results: List[float], max_experiments_limit: int = 50
    ) -> ParameterSweepResult:
        if len(param_grid) > max_experiments_limit:
            raise ValueError(f"Parameter sweep grid size ({len(param_grid)}) exceeds safety limit ({max_experiments_limit})")

        std_sharpe = float(np.std(sharpe_results)) if sharpe_results else 0.0
        is_sensitive = std_sharpe > 0.5  # High sensitivity across parameters indicates potential overfitting

        return ParameterSweepResult(
            parameter_grid=param_grid,
            sharpe_scores=sharpe_results,
            parameter_sensitivity_std=round(std_sharpe, 4),
            is_highly_sensitive=is_sensitive
        )
