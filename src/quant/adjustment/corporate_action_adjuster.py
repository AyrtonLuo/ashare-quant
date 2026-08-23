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

Two algorithm versions coexist (CORPORATE_ACTION_UNIFIED_FORMULA_ARCHITECTURE_PROPOSAL.md,
CEO-approved, `STOCK_SPLIT` explicitly out of scope for both):

- `algorithm_version="1.0"` (legacy, byte-identical to pre-unification behavior): each event's
  factor is computed independently from RAW prices against a single shared `reference_price`
  (the raw close on/after `ex_date`), then multiplied together for events sharing an `ex_date`.
  - STOCK_SPLIT (split_ratio S): multiplied by 1/S.
  - BONUS_ISSUE (bonus_ratio B): multiplied by 1/(1+B).
  - CASH_DIVIDEND (cash_amount_per_share D): multiplied by (P-D)/P, P=reference_price. Requires
    D < P; fails closed otherwise.
  - RIGHTS_OFFERING (rights_ratio R, subscription_price Pr): multiplied by (P+R·Pr)/(P·(1+R)),
    P=reference_price. subscription_price >= P is legitimate (factor >= 1.0), not an error.
- `algorithm_version="2.0"` (canonical, docs/CORPORATE_ACTION_SPECIFICATION.md §2): uses `P_pre`
  (the raw close strictly before `ex_date`) instead of `reference_price` throughout. STOCK_SPLIT
  and BONUS_ISSUE are unaffected by the version (no price dependency either way). CASH_DIVIDEND
  alone still uses (P_pre-D)/P_pre. If a RIGHTS_OFFERING event shares an `ex_date` with a
  CASH_DIVIDEND and/or BONUS_ISSUE event, the group's `D`/`B`/`R` factor is computed as ONE
  unified fraction, `(P_pre - D + Pr·R) / (1 + B + R)`, rather than as a product of independent
  factors — the two are NOT algebraically equivalent whenever `RIGHTS_OFFERING` is combined with
  anything else (verified numerically; every `D`/`B`(/`S`) combination WITHOUT `RIGHTS_OFFERING`
  is already exactly equal to the unified formula once `P_pre` is used, so only the
  `RIGHTS_OFFERING`-combined case needs this separate path). `STOCK_SPLIT`, if present in the
  same group, is never an input to this unified computation — its own `1/S` factor is always
  multiplied on top independently, under both versions.

`adjust()` takes `algorithm_version` as an explicit keyword argument. Production call sites
(`CertifiedResearchRunExecutor.execute()`, `CertifiedReplayEngine.replay()`) always pass it
explicitly and never rely on the default; the default exists only so pre-existing test call
sites that predate versioning keep exercising `"1.0"` (today's behavior) unmodified.

Each event's factor (or, for `"2.0"` `RIGHTS_OFFERING` combinations, the combined `D`/`B`/`R`
factor) is computed independently from RAW prices (never from an already-adjusted price), so
factors compose correctly regardless of processing order.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict

from src.data.contracts.corporate_action import CorporateActionContract
from src.data.validation.pit_gate import PITGate

SUPPORTED_ADJUSTING_ACTION_TYPES = {"STOCK_SPLIT", "BONUS_ISSUE", "CASH_DIVIDEND", "RIGHTS_OFFERING"}
LEGACY_ALGORITHM_VERSION = "1.0"
UNIFIED_ALGORITHM_VERSION = "2.0"


@dataclass(frozen=True)
class AdjustedPriceSeries:
    dates: List[str]
    raw_prices: List[float]
    adjusted_prices: List[float]
    adj_factors: List[float]        # cumulative multiplier applied at each date (1.0 = unaffected)
    actions_applied: List[str]      # "action_type:ex_date" identifiers actually folded in, for audit


class CorporateActionAdjuster:
    """Applies split / bonus / cash-dividend / rights-offering backward adjustment to a dated
    raw price series."""

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
            if action.rights_ratio is None or action.subscription_price is None:
                raise ValueError(
                    f"FAIL CLOSED: RIGHTS_OFFERING action for {action.symbol} on {action.ex_date} "
                    "is missing rights_ratio or subscription_price; refusing to treat a missing "
                    "field as ratio 0.0."
                )
            if action.rights_ratio <= 0:
                raise ValueError(
                    f"FAIL CLOSED: invalid rights_ratio {action.rights_ratio} for {action.symbol} "
                    f"on {action.ex_date}."
                )
            if action.subscription_price <= 0:
                raise ValueError(
                    f"FAIL CLOSED: invalid subscription_price {action.subscription_price} for "
                    f"{action.symbol} on {action.ex_date}."
                )
            if reference_price <= 0:
                raise ValueError(
                    f"FAIL CLOSED: cannot compute rights-offering adjustment with non-positive "
                    f"reference price for {action.symbol} on {action.ex_date}."
                )
            # subscription_price >= reference_price is deliberately NOT an error here (unlike
            # CASH_DIVIDEND's D >= P case) — it produces a well-defined factor >= 1.0, a
            # legitimate outcome for a weak-demand rights issue priced near or above market.
            return (reference_price + action.rights_ratio * action.subscription_price) / (
                reference_price * (1.0 + action.rights_ratio)
            )

        raise ValueError(
            f"FAIL CLOSED: unknown corporate action_type '{action.action_type}' for {action.symbol} "
            f"on {action.ex_date}."
        )

    @staticmethod
    def _combined_dbr_factor(events: List[CorporateActionContract], p_pre: float) -> float:
        """algorithm_version="2.0" only: unified D/B/R factor for a same-ex_date group containing
        a RIGHTS_OFFERING event plus, optionally, CASH_DIVIDEND and/or BONUS_ISSUE — never
        STOCK_SPLIT, which is always applied independently by the caller (see module docstring).
        Implements docs/CORPORATE_ACTION_SPECIFICATION.md §2:
            P_ex = (P_pre - D + Pr*R) / (1 + B + R)
        """
        symbol = events[0].symbol
        ex_date = events[0].ex_date
        D, B, R, Pr = 0.0, 0.0, None, None

        for e in events:
            if e.action_type == "CASH_DIVIDEND":
                if e.cash_amount_per_share < 0:
                    raise ValueError(f"FAIL CLOSED: negative cash_amount_per_share for {symbol} on {ex_date}.")
                D = e.cash_amount_per_share
            elif e.action_type == "BONUS_ISSUE":
                if e.bonus_ratio < 0:
                    raise ValueError(f"FAIL CLOSED: invalid bonus_ratio {e.bonus_ratio} for {symbol} on {ex_date}.")
                B = e.bonus_ratio
            elif e.action_type == "RIGHTS_OFFERING":
                if e.rights_ratio is None or e.subscription_price is None:
                    raise ValueError(
                        f"FAIL CLOSED: RIGHTS_OFFERING action for {symbol} on {ex_date} is missing "
                        "rights_ratio or subscription_price; refusing to treat a missing field as ratio 0.0."
                    )
                if e.rights_ratio <= 0:
                    raise ValueError(f"FAIL CLOSED: invalid rights_ratio {e.rights_ratio} for {symbol} on {ex_date}.")
                if e.subscription_price <= 0:
                    raise ValueError(
                        f"FAIL CLOSED: invalid subscription_price {e.subscription_price} for {symbol} on {ex_date}."
                    )
                R, Pr = e.rights_ratio, e.subscription_price
            else:
                raise ValueError(
                    f"FAIL CLOSED: unexpected action_type '{e.action_type}' in unified D/B/R computation "
                    f"for {symbol} on {ex_date} — STOCK_SPLIT must never reach this path."
                )

        if R is None:
            raise ValueError(
                f"FAIL CLOSED: unified D/B/R computation for {symbol} on {ex_date} requires a "
                "RIGHTS_OFFERING event to be present."
            )
        if p_pre <= 0:
            raise ValueError(
                f"FAIL CLOSED: cannot compute unified adjustment with non-positive P_pre for {symbol} on {ex_date}."
            )

        numerator = p_pre - D + Pr * R
        if numerator <= 0:
            raise ValueError(
                f"FAIL CLOSED: unified adjustment for {symbol} on {ex_date} would produce a non-positive "
                f"ex-price (P_pre={p_pre}, D={D}, Pr={Pr}, R={R}); refusing to emit a nonsensical series."
            )
        # P_ex = numerator / (1+B+R); the adjustment FACTOR applied to pre-event prices is
        # P_ex / P_pre — dividing by p_pre here as well is not optional, it's what turns the
        # spec's ex-price into the multiplicative ratio adjust() actually applies.
        return numerator / (p_pre * (1.0 + B + R))

    @classmethod
    def adjust(
        cls,
        dates: List[str],
        raw_prices: List[float],
        actions: List[CorporateActionContract],
        as_of: datetime,
        algorithm_version: str = LEGACY_ALGORITHM_VERSION,
    ) -> AdjustedPriceSeries:
        """Returns a PIT-correct adjusted price series. `dates` must be sorted ascending and
        aligned 1:1 with `raw_prices`. Only actions visible as of `as_of` are applied.
        `algorithm_version` selects "1.0" (legacy, default — see module docstring) or "2.0"
        (unified formula). Production callers must always pass this explicitly; the default
        exists only for call sites that predate versioning and intend legacy behavior."""
        if algorithm_version not in (LEGACY_ALGORITHM_VERSION, UNIFIED_ALGORITHM_VERSION):
            raise ValueError(f"FAIL CLOSED: unknown algorithm_version '{algorithm_version}'.")
        if len(dates) != len(raw_prices):
            raise ValueError("FAIL CLOSED: dates and raw_prices length mismatch.")
        if dates != sorted(dates):
            raise ValueError("FAIL CLOSED: dates must be sorted ascending for adjustment to be well-defined.")

        visible_actions = PITGate.filter_pit_corporate_actions(actions, as_of)

        by_ex_date: Dict[str, List[CorporateActionContract]] = {}
        for a in visible_actions:
            if a.action_type not in SUPPORTED_ADJUSTING_ACTION_TYPES:
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

            # Reference price ("1.0"): raw close on/after ex_date. P_pre ("2.0"): raw close
            # strictly before ex_date — both derived from the same already-computed idx_before.
            ref_idx = idx_before + 1 if idx_before + 1 < n else idx_before
            reference_price = raw_prices[ref_idx]
            p_pre = raw_prices[idx_before]

            has_rights = algorithm_version == UNIFIED_ALGORITHM_VERSION and any(
                e.action_type == "RIGHTS_OFFERING" for e in events
            )

            if has_rights:
                # "2.0" unified path: STOCK_SPLIT (if present) is never part of the D/B/R
                # computation — it is applied independently, exactly as under "1.0".
                split_events = [e for e in events if e.action_type == "STOCK_SPLIT"]
                dbr_events = [e for e in events if e.action_type != "STOCK_SPLIT"]

                combined_factor = cls._combined_dbr_factor(dbr_events, p_pre)
                for i in range(0, idx_before + 1):
                    adj_factors[i] *= combined_factor
                applied.extend(f"{e.action_type}:{e.ex_date}" for e in dbr_events)

                for e in split_events:
                    factor = cls._event_factor(e, reference_price)
                    for i in range(0, idx_before + 1):
                        adj_factors[i] *= factor
                    applied.append(f"{e.action_type}:{e.ex_date}")
            else:
                # "1.0" (always), or "2.0" without RIGHTS_OFFERING (already exactly equal to the
                # unified formula once the correct price basis is used — see module docstring).
                price_basis = p_pre if algorithm_version == UNIFIED_ALGORITHM_VERSION else reference_price
                for event in events:
                    factor = cls._event_factor(event, price_basis)
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
