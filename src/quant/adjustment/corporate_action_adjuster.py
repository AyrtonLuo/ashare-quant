"""
corporate_action_adjuster.py — PIT-correct corporate-action price adjustment.

Computes a backward-adjusted ("ADJUSTED") price series from a RAW, dated price series plus
a set of corporate action events. RAW and ADJUSTED series are always returned as distinct
fields on `AdjustedPriceSeries` so a caller can never accidentally conflate or double-apply
adjustment — there is exactly one place in the codebase that performs this computation, and
callers consume its output rather than re-deriving factors themselves.

PIT correctness: only actions with `available_at <= as_of` may influence the series (see
PITGate.filter_pit_corporate_actions). An action's `ex_date` (effective date) is never used
as a substitute for its PIT visibility.

Adjustment convention (standard backward/back-adjustment):
- STOCK_SPLIT (split_ratio R, e.g. 2.0 for a 1-for-2 split): dates strictly before ex_date are
  multiplied by 1/R, bringing pre-split prices onto the post-split share-count scale.
- BONUS_ISSUE (bonus_ratio B, additional shares per share held): dates strictly before ex_date
  are multiplied by 1/(1+B), same rationale as a split.
- CASH_DIVIDEND (cash_amount_per_share D): dates strictly before ex_date are multiplied by
  (P - D) / P, where P is the raw close on/after ex_date (the reference price). This is the
  standard ex-dividend adjustment factor and requires D < P; a dividend that would produce a
  non-positive adjustment factor fails closed rather than emitting a nonsensical series.
- RIGHTS_OFFERING is not implemented: rather than guess an adjustment formula that has not
  been reviewed, this fails closed.

Each event's factor is computed independently from RAW prices (never from an
already-adjusted price), so factors compose correctly regardless of processing order.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict

from src.data.contracts.corporate_action import CorporateActionContract
from src.data.validation.pit_gate import PITGate

SUPPORTED_ADJUSTING_ACTION_TYPES = {"STOCK_SPLIT", "BONUS_ISSUE", "CASH_DIVIDEND"}


@dataclass(frozen=True)
class AdjustedPriceSeries:
    dates: List[str]
    raw_prices: List[float]
    adjusted_prices: List[float]
    adj_factors: List[float]        # cumulative multiplier applied at each date (1.0 = unaffected)
    actions_applied: List[str]      # "action_type:ex_date" identifiers actually folded in, for audit


class CorporateActionAdjuster:
    """Applies split / bonus / cash-dividend backward adjustment to a dated raw price series."""

    @staticmethod
    def _event_factor(action: CorporateActionContract, reference_price: float) -> float:
        if action.action_type == "STOCK_SPLIT":
            if action.split_ratio <= 0:
                raise ValueError(
                    f"FAIL CLOSED: invalid split_ratio {action.split_ratio} for {action.symbol} "
                    f"on {action.ex_date}."
                )
            return 1.0 / action.split_ratio

        if action.action_type == "BONUS_ISSUE":
            if action.bonus_ratio < 0:
                raise ValueError(
                    f"FAIL CLOSED: invalid bonus_ratio {action.bonus_ratio} for {action.symbol} "
                    f"on {action.ex_date}."
                )
            return 1.0 / (1.0 + action.bonus_ratio)

        if action.action_type == "CASH_DIVIDEND":
            if reference_price <= 0:
                raise ValueError(
                    f"FAIL CLOSED: cannot compute dividend adjustment with non-positive reference "
                    f"price for {action.symbol} on {action.ex_date}."
                )
            if action.cash_amount_per_share >= reference_price:
                raise ValueError(
                    f"FAIL CLOSED: cash dividend {action.cash_amount_per_share} >= reference price "
                    f"{reference_price} for {action.symbol} on {action.ex_date}; refusing to produce "
                    "a non-positive adjustment factor."
                )
            if action.cash_amount_per_share < 0:
                raise ValueError(
                    f"FAIL CLOSED: negative cash_amount_per_share for {action.symbol} on {action.ex_date}."
                )
            return (reference_price - action.cash_amount_per_share) / reference_price

        if action.action_type == "RIGHTS_OFFERING":
            raise ValueError(
                f"FAIL CLOSED: RIGHTS_OFFERING adjustment is not implemented for {action.symbol} "
                f"on {action.ex_date}; refusing to silently ignore it or guess a formula."
            )

        raise ValueError(
            f"FAIL CLOSED: unknown corporate action_type '{action.action_type}' for {action.symbol} "
            f"on {action.ex_date}."
        )

    @classmethod
    def adjust(
        cls,
        dates: List[str],
        raw_prices: List[float],
        actions: List[CorporateActionContract],
        as_of: datetime,
    ) -> AdjustedPriceSeries:
        """Returns a PIT-correct adjusted price series. `dates` must be sorted ascending and
        aligned 1:1 with `raw_prices`. Only actions visible as of `as_of` are applied."""
        if len(dates) != len(raw_prices):
            raise ValueError("FAIL CLOSED: dates and raw_prices length mismatch.")
        if dates != sorted(dates):
            raise ValueError("FAIL CLOSED: dates must be sorted ascending for adjustment to be well-defined.")

        visible_actions = PITGate.filter_pit_corporate_actions(actions, as_of)

        by_ex_date: Dict[str, List[CorporateActionContract]] = {}
        for a in visible_actions:
            if a.action_type not in SUPPORTED_ADJUSTING_ACTION_TYPES and a.action_type != "RIGHTS_OFFERING":
                raise ValueError(f"FAIL CLOSED: unknown corporate action_type '{a.action_type}' for {a.symbol}.")
            by_ex_date.setdefault(a.ex_date, []).append(a)

        n = len(dates)
        adj_factors = [1.0] * n
        applied: List[str] = []

        for ex_date, events in by_ex_date.items():
            # idx_before = last index i such that dates[i] < ex_date (dates strictly before the event)
            idx_before = None
            for i in range(n):
                if dates[i] < ex_date:
                    idx_before = i
            if idx_before is None:
                continue  # event's ex_date is at or before the window start; nothing to adjust

            # Reference price: raw close on/after ex_date (standard ex-dividend/ex-split anchor).
            ref_idx = idx_before + 1 if idx_before + 1 < n else idx_before
            reference_price = raw_prices[ref_idx]

            for event in events:
                factor = cls._event_factor(event, reference_price)
                for i in range(0, idx_before + 1):
                    adj_factors[i] *= factor
                applied.append(f"{event.action_type}:{event.ex_date}")

        adjusted_prices = [round(raw_prices[i] * adj_factors[i], 6) for i in range(n)]

        return AdjustedPriceSeries(
            dates=list(dates),
            raw_prices=list(raw_prices),
            adjusted_prices=adjusted_prices,
            adj_factors=adj_factors,
            actions_applied=applied,
        )
