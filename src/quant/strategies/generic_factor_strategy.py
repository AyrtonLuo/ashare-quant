"""
generic_factor_strategy.py — Generic signal-ranking strategy (Phase 8A).

Independent implementation of BaseStrategy — deliberately does NOT subclass
SimpleMomentumStrategy, per explicit CEO architectural ruling (see
docs/PHASE_8A_ARCHITECTURE_PROPOSAL.md §14): the ranking/top-N/equal-weight logic here is
identical in shape to SimpleMomentumStrategy's, but a composite Momentum+Value signal
certified under a class literally named "MomentumStrategy" would misrepresent what actually
drove the portfolio in the audit trail. SimpleMomentumStrategy is left untouched, with its own
test suite unmodified, precisely because there is no real inheritance relationship between
"a strategy driven by momentum specifically" and "a strategy driven by whatever factors were
configured" — duplicating the ~10 lines of logic honestly is preferred over an inheritance
relationship that doesn't conceptually exist.
"""

from typing import List, Dict
from src.quant.strategies.base import BaseStrategy
from src.quant.signals.engine import SignalRecommendation


class GenericFactorStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "generic_factor_strategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    def generate_target_portfolio(
        self, signals: List[SignalRecommendation], top_n: int = 5
    ) -> Dict[str, float]:
        """Ranks BUY-biased signals by signal_score descending, takes the top N, equal-weights
        them. Zero qualifying candidates is a valid, fully-cash result (empty dict), not a
        failure — a factor-driven strategy finding nothing worth holding today is a legitimate
        research outcome."""
        candidates = [s for s in signals if s.signal_score > 0]
        sorted_candidates = sorted(candidates, key=lambda s: s.signal_score, reverse=True)

        selected = sorted_candidates[:top_n]
        if not selected:
            return {}

        weight = round(1.0 / len(selected), 4)
        return {s.symbol: weight for s in selected}
