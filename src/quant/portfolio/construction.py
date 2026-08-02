"""
construction.py — Portfolio Construction Engine enforcing sum(weights) <= 1.0 & tradability.
"""

from dataclasses import dataclass
from typing import Dict, List
from src.data.domain.security_master import SecurityMasterRegistry


@dataclass(frozen=True)
class PortfolioTarget:
    effective_date: str
    strategy_id: str
    weights: Dict[str, float]
    total_exposure: float


class PortfolioConstructor:
    """Validates target weights, handles suspended/delisted assets, and computes exposure."""

    @staticmethod
    def build_portfolio(
        raw_weights: Dict[str, float],
        effective_date: str,
        strategy_id: str,
        security_registry: SecurityMasterRegistry
    ) -> PortfolioTarget:
        valid_weights = {}
        for symbol, w in raw_weights.items():
            if security_registry.is_tradable_on(symbol, effective_date):
                valid_weights[symbol] = w

        total_w = sum(valid_weights.values())
        if total_w > 1.0:
            # Re-normalize to sum to 1.0
            valid_weights = {s: round(w / total_w, 4) for s, w in valid_weights.items()}

        total_exposure = round(sum(valid_weights.values()), 4)

        return PortfolioTarget(
            effective_date=effective_date,
            strategy_id=strategy_id,
            weights=valid_weights,
            total_exposure=total_exposure
        )
