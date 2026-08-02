"""
construction_v2.py — Portfolio Construction V2 with Position Limits, Turnover Control & Score Weighting.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from src.data.domain.security_master import SecurityMasterRegistry


@dataclass(frozen=True)
class PortfolioTargetV2:
    effective_date: str
    strategy_id: str
    weights: Dict[str, float]
    total_exposure: float
    turnover: float


class PortfolioConstructorV2:
    """Enforces Position Caps (e.g. max 20%), Turnover Limits, and Tradability filtering."""

    @staticmethod
    def build_portfolio_v2(
        composite_scores: Dict[str, float],
        previous_weights: Dict[str, float],
        effective_date: str,
        strategy_id: str,
        security_registry: SecurityMasterRegistry,
        max_position_limit: float = 0.20,
        max_turnover_limit: float = 0.50,
        top_n: int = 5
    ) -> PortfolioTargetV2:
        # Filter tradable assets
        tradable = {s: sc for s, sc in composite_scores.items() if security_registry.is_tradable_on(s, effective_date)}
        
        if not tradable:
            return PortfolioTargetV2(effective_date, strategy_id, {}, 0.0, 0.0)

        # Sort top N
        sorted_symbols = sorted(tradable.keys(), key=lambda s: tradable[s], reverse=True)[:top_n]
        
        # Raw Equal/Score Weight
        raw_w = 1.0 / len(sorted_symbols)
        target_weights = {}
        for s in sorted_symbols:
            # Enforce Max Position Cap
            target_weights[s] = round(min(raw_w, max_position_limit), 4)

        # Calculate Turnover
        all_syms = set(previous_weights.keys()) | set(target_weights.keys())
        turnover = sum(abs(target_weights.get(s, 0.0) - previous_weights.get(s, 0.0)) for s in all_syms) / 2.0
        
        # If turnover exceeds limit, scale back trade size towards previous weights
        if turnover > max_turnover_limit and previous_weights:
            scale = max_turnover_limit / turnover
            constrained_weights = {}
            for s in all_syms:
                old_w = previous_weights.get(s, 0.0)
                new_w = target_weights.get(s, 0.0)
                adj_w = old_w + (new_w - old_w) * scale
                if adj_w > 0.001:
                    constrained_weights[s] = round(min(adj_w, max_position_limit), 4)
            target_weights = constrained_weights
            turnover = max_turnover_limit

        total_exposure = round(sum(target_weights.values()), 4)

        return PortfolioTargetV2(
            effective_date=effective_date,
            strategy_id=strategy_id,
            weights=target_weights,
            total_exposure=total_exposure,
            turnover=round(turnover, 4)
        )
