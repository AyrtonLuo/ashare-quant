"""
test_corporate_action_integration.py — Phase 7I adversarial tests (Directive 007I, Section 6).

Proves corporate actions are actually consumed by the backtest calculation path, that
availability is PIT-correct, that revisions are immutable, that replay is deterministic,
and that the backtest result measurably changes because of corporate-action adjustment
(not merely that a CorporateActionContract object round-trips its own fields).
"""

from datetime import datetime
import pytest

from src.data.contracts.corporate_action import CorporateActionContract
from src.data.revision.corporate_action_store import CorporateActionStore
from src.data.validation.pit_gate import PITGate
from src.quant.adjustment.corporate_action_adjuster import CorporateActionAdjuster
from src.quant.backtest.engine import BacktestEngine
from src.quant.portfolio.construction import PortfolioTarget


def _split_action(available_at=datetime(2026, 7, 20, 15, 0)):
    return CorporateActionContract(
        symbol="600519.SH", ex_date="2026-08-04", action_type="STOCK_SPLIT",
        cash_amount_per_share=0.0, bonus_ratio=0.0, split_ratio=2.0,
        announcement_date="2026-07-20", available_at=available_at, received_at=available_at,
        quality_status="VALID",
    )


def _dividend_action(available_at=datetime(2026, 7, 20, 15, 0)):
    return CorporateActionContract(
        symbol="600519.SH", ex_date="2026-08-04", action_type="CASH_DIVIDEND",
        cash_amount_per_share=10.0, bonus_ratio=0.0, split_ratio=1.0,
        announcement_date="2026-07-20", available_at=available_at, received_at=available_at,
        quality_status="VALID",
    )


def _rights_action(rights_ratio=0.3, subscription_price=6.0, available_at=datetime(2026, 7, 20, 15, 0)):
    return CorporateActionContract(
        symbol="600519.SH", ex_date="2026-08-04", action_type="RIGHTS_OFFERING",
        cash_amount_per_share=0.0, bonus_ratio=0.0, split_ratio=1.0,
        announcement_date="2026-07-20", available_at=available_at, received_at=available_at,
        quality_status="VALID", rights_ratio=rights_ratio, subscription_price=subscription_price,
    )


DATES = ["2026-08-01", "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"]
AS_OF_LATE = datetime(2026, 8, 10)


# --- TEST A: split — unadjusted shows mechanical discontinuity, adjusted does not -----------

def test_split_unadjusted_shows_discontinuity_adjusted_does_not():
    raw = [100.0, 100.0, 50.0, 50.0, 50.0]  # mechanical halving at the split date
    result = CorporateActionAdjuster.adjust(DATES, raw, [_split_action()], AS_OF_LATE)

    # Unadjusted (raw) series has a -50% single-day return at the split boundary.
    raw_day_return = (raw[2] - raw[1]) / raw[1]
    assert raw_day_return == pytest.approx(-0.5)

    # Adjusted series must be flat across the same boundary (no false economic return).
    adj_day_return = (result.adjusted_prices[2] - result.adjusted_prices[1]) / result.adjusted_prices[1]
    assert adj_day_return == pytest.approx(0.0, abs=1e-9)
    assert result.adjusted_prices == [50.0, 50.0, 50.0, 50.0, 50.0]


# --- TEST B: cash dividend — correct ex-dividend adjustment applied -------------------------

def test_cash_dividend_applies_ex_dividend_adjustment():
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]  # price drops by dividend amount on ex-date
    result = CorporateActionAdjuster.adjust(DATES, raw, [_dividend_action()], AS_OF_LATE)

    expected_factor = (90.0 - 10.0) / 90.0  # (ref_price - dividend) / ref_price
    assert result.adj_factors[0] == pytest.approx(expected_factor)
    assert result.adj_factors[1] == pytest.approx(expected_factor)
    assert result.adj_factors[2] == pytest.approx(1.0)
    # Adjusted return across the ex-date boundary reflects total return, not a fabricated drop.
    adj_day_return = (result.adjusted_prices[2] - result.adjusted_prices[1]) / result.adjusted_prices[1]
    assert adj_day_return > -0.02  # nowhere near the raw -10% mechanical drop


def test_dividend_gte_reference_price_fails_closed():
    raw = [100.0, 100.0, 5.0, 5.0, 5.0]
    bad_dividend = CorporateActionContract(
        symbol="600519.SH", ex_date="2026-08-04", action_type="CASH_DIVIDEND",
        cash_amount_per_share=10.0, bonus_ratio=0.0, split_ratio=1.0,
        announcement_date="2026-07-20",
        available_at=datetime(2026, 7, 20), received_at=datetime(2026, 7, 20),
        quality_status="VALID",
    )
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CorporateActionAdjuster.adjust(DATES, raw, [bad_dividend], AS_OF_LATE)


# --- TEST C: available_at > as_of => historical snapshot must NOT use the action ------------

def test_action_not_yet_available_is_excluded_from_snapshot():
    raw = [100.0, 100.0, 50.0, 50.0, 50.0]
    future_action = _split_action(available_at=datetime(2026, 8, 9))  # disclosed AFTER as_of below
    as_of_before_disclosure = datetime(2026, 8, 5)

    result = CorporateActionAdjuster.adjust(DATES, raw, [future_action], as_of_before_disclosure)
    assert result.adjusted_prices == raw
    assert result.actions_applied == []


# --- TEST D: effective_date <= as_of but available_at > as_of => still excluded -------------

def test_effective_date_before_as_of_but_available_at_after_is_excluded():
    raw = [100.0, 100.0, 50.0, 50.0, 50.0]
    # ex_date (2026-08-04) is well before as_of, but available_at is AFTER as_of.
    action = _split_action(available_at=datetime(2026, 8, 20))
    as_of = datetime(2026, 8, 10)  # after ex_date, before available_at

    assert action.ex_date <= as_of.strftime("%Y-%m-%d")  # effective_date condition satisfied
    assert action.available_at > as_of                    # availability condition NOT satisfied

    result = CorporateActionAdjuster.adjust(DATES, raw, [action], as_of)
    assert result.adjusted_prices == raw, "action must not be visible: available_at > as_of"

    visible = PITGate.filter_pit_corporate_actions([action], as_of)
    assert visible == []


# --- TEST E: revision — old revision immutable, PIT query sees what was actually available --

def test_corporate_action_revision_immutability_and_pit_correctness():
    store = CorporateActionStore()

    original = CorporateActionContract(
        symbol="600519.SH", ex_date="2026-08-04", action_type="CASH_DIVIDEND",
        cash_amount_per_share=10.0, bonus_ratio=0.0, split_ratio=1.0,
        announcement_date="2026-07-20",
        available_at=datetime(2026, 7, 20), received_at=datetime(2026, 7, 20),
        quality_status="VALID",
    )
    store.add_action(original)

    # Later, the disclosed amount is corrected (restated) with a new available_at.
    corrected = CorporateActionContract(
        symbol="600519.SH", ex_date="2026-08-04", action_type="CASH_DIVIDEND",
        cash_amount_per_share=12.5, bonus_ratio=0.0, split_ratio=1.0,
        announcement_date="2026-08-01",
        available_at=datetime(2026, 8, 1), received_at=datetime(2026, 8, 1),
        quality_status="VALID",
    )
    store.add_action(corrected)

    # A historical snapshot as_of before the correction must still see the ORIGINAL value.
    as_of_before_correction = datetime(2026, 7, 25)
    seen = store.query_pit("600519.SH", "2026-08-04", "CASH_DIVIDEND", as_of_before_correction)
    assert seen.cash_amount_per_share == 10.0

    # A snapshot as_of after the correction sees the corrected value.
    as_of_after_correction = datetime(2026, 8, 5)
    seen2 = store.query_pit("600519.SH", "2026-08-04", "CASH_DIVIDEND", as_of_after_correction)
    assert seen2.cash_amount_per_share == 12.5

    # The original revision is never mutated or removed from history.
    history = store.get_history("600519.SH", "2026-08-04", "CASH_DIVIDEND")
    assert len(history) == 2
    assert history[0].cash_amount_per_share == 10.0
    assert history[1].cash_amount_per_share == 12.5


# --- TEST F: same inputs twice => identical result hash (determinism) -----------------------

def test_same_corporate_action_adjusted_backtest_is_deterministic():
    raw = [100.0, 100.0, 50.0, 50.0, 50.0]
    targets = [PortfolioTarget("2026-08-01", "strat_test", {"600519.SH": 1.0}, 1.0)]

    def run_once():
        adjusted = CorporateActionAdjuster.adjust(DATES, raw, [_split_action()], AS_OF_LATE)
        engine = BacktestEngine()
        return engine.run_backtest(
            dataset_id="ds_test", strategy_id="strat_test",
            daily_prices={"600519.SH": adjusted.adjusted_prices}, portfolio_targets=targets,
        )

    r1 = run_once()
    r2 = run_once()
    assert r1.total_return == r2.total_return
    assert r1.sharpe_ratio == r2.sharpe_ratio
    assert r1.equity_curve == r2.equity_curve


# --- TEST G: the backtest result actually, measurably changes because of the corp action ----

def test_backtest_result_measurably_changes_from_corporate_action_consumption():
    """The most important regression test: prove the pipeline does not merely store corporate
    action objects and ignore them. Running the same raw price series through the backtest
    engine WITH vs WITHOUT corporate-action adjustment must produce different, and specifically
    more economically correct, results."""
    raw = [100.0, 100.0, 50.0, 50.0, 55.0]
    targets = [PortfolioTarget("2026-08-01", "strat_test", {"600519.SH": 1.0}, 1.0)]
    engine = BacktestEngine()

    result_raw = engine.run_backtest(
        dataset_id="ds_test", strategy_id="strat_test",
        daily_prices={"600519.SH": raw}, portfolio_targets=targets,
    )

    adjusted = CorporateActionAdjuster.adjust(DATES, raw, [_split_action()], AS_OF_LATE)
    result_adjusted = engine.run_backtest(
        dataset_id="ds_test", strategy_id="strat_test",
        daily_prices={"600519.SH": adjusted.adjusted_prices}, portfolio_targets=targets,
    )

    # Consumption proof: the two runs must diverge because adjustment changed the input series.
    assert result_raw.total_return != result_adjusted.total_return
    assert result_raw.max_drawdown != result_adjusted.max_drawdown

    # Correctness proof: the RAW run shows a large fabricated drawdown from the mechanical
    # split discontinuity that the ADJUSTED run must not exhibit.
    assert result_raw.max_drawdown > result_adjusted.max_drawdown


# --- TEST H: RIGHTS_OFFERING (配股) — RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md -----

def test_rights_offering_applies_dilution_adjustment():
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    action = _rights_action(rights_ratio=0.3, subscription_price=6.0)  # discount to reference 90.0
    result = CorporateActionAdjuster.adjust(DATES, raw, [action], AS_OF_LATE)

    expected_factor = (90.0 + 0.3 * 6.0) / (90.0 * (1.0 + 0.3))
    assert expected_factor < 1.0
    assert result.adj_factors[0] == pytest.approx(expected_factor)
    assert result.adj_factors[1] == pytest.approx(expected_factor)
    assert result.adj_factors[2] == pytest.approx(1.0)


def test_rights_offering_at_market_price_produces_no_adjustment():
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    action = _rights_action(rights_ratio=0.3, subscription_price=90.0)  # priced at reference price
    result = CorporateActionAdjuster.adjust(DATES, raw, [action], AS_OF_LATE)
    assert result.adj_factors[0] == pytest.approx(1.0)
    assert result.adjusted_prices == raw


def test_rights_offering_zero_ratio_fails_closed():
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    action = _rights_action(rights_ratio=0.0, subscription_price=6.0)
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CorporateActionAdjuster.adjust(DATES, raw, [action], AS_OF_LATE)


def test_rights_offering_negative_ratio_fails_closed():
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    action = _rights_action(rights_ratio=-0.1, subscription_price=6.0)
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CorporateActionAdjuster.adjust(DATES, raw, [action], AS_OF_LATE)


def test_rights_offering_non_positive_subscription_price_fails_closed():
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    action = _rights_action(rights_ratio=0.3, subscription_price=0.0)
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CorporateActionAdjuster.adjust(DATES, raw, [action], AS_OF_LATE)


def test_rights_offering_missing_ratio_fails_closed():
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    action = _rights_action(rights_ratio=None, subscription_price=6.0)
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CorporateActionAdjuster.adjust(DATES, raw, [action], AS_OF_LATE)


def test_rights_offering_missing_subscription_price_fails_closed():
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    action = _rights_action(rights_ratio=0.3, subscription_price=None)
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CorporateActionAdjuster.adjust(DATES, raw, [action], AS_OF_LATE)


def test_rights_offering_subscription_price_above_reference_produces_valid_factor_gte_one():
    """CEO-confirmed (RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md §3.2/§4.2): unlike
    CASH_DIVIDEND's D >= P fail-closed rule, subscription_price >= reference_price is a
    legitimate, if unusual, real-world outcome (a weak-demand rights issue) and must NOT raise."""
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    action = _rights_action(rights_ratio=0.3, subscription_price=100.0)  # above reference 90.0
    result = CorporateActionAdjuster.adjust(DATES, raw, [action], AS_OF_LATE)
    expected_factor = (90.0 + 0.3 * 100.0) / (90.0 * 1.3)
    assert expected_factor >= 1.0
    assert result.adj_factors[0] == pytest.approx(expected_factor)


def test_rights_offering_excluded_when_available_at_after_as_of():
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    future_action = _rights_action(available_at=datetime(2026, 8, 9))  # disclosed AFTER as_of below
    as_of_before_disclosure = datetime(2026, 8, 5)

    result = CorporateActionAdjuster.adjust(DATES, raw, [future_action], as_of_before_disclosure)
    assert result.adjusted_prices == raw
    assert result.actions_applied == []


def test_rights_offering_backward_compatible_construction_without_new_fields():
    """An old-style construction call (only the fields that predate this proposal) must still
    work — proves the two new trailing-defaulted fields don't perturb any existing call site."""
    action = _split_action()
    assert action.rights_ratio is None
    assert action.subscription_price is None


def test_rights_offering_combined_with_cash_dividend_same_ex_date_multiplies_factors():
    """RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md §3.3: two actions sharing one ex_date
    multiply their independently-computed factors against the same shared reference_price —
    proven here against a value computed independently in the test, not asserted to match
    docs/CORPORATE_ACTION_SPECIFICATION.md's unified formula (§3.3 shows those are not the same
    computation for the combined case — that reconciliation remains a separate future item)."""
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    dividend = _dividend_action()  # cash_amount_per_share=10.0
    rights = _rights_action(rights_ratio=0.3, subscription_price=6.0)
    result = CorporateActionAdjuster.adjust(DATES, raw, [dividend, rights], AS_OF_LATE)

    f_dividend = (90.0 - 10.0) / 90.0
    f_rights = (90.0 + 0.3 * 6.0) / (90.0 * 1.3)
    expected = f_dividend * f_rights
    assert result.adj_factors[0] == pytest.approx(expected)
    assert result.adj_factors[1] == pytest.approx(expected)
    assert result.adj_factors[2] == pytest.approx(1.0)
    assert set(result.actions_applied) == {"CASH_DIVIDEND:2026-08-04", "RIGHTS_OFFERING:2026-08-04"}


def test_rights_offering_combined_with_bonus_issue_same_ex_date_multiplies_factors():
    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    bonus = CorporateActionContract(
        symbol="600519.SH", ex_date="2026-08-04", action_type="BONUS_ISSUE",
        cash_amount_per_share=0.0, bonus_ratio=0.2, split_ratio=1.0,
        announcement_date="2026-07-20",
        available_at=datetime(2026, 7, 20, 15, 0), received_at=datetime(2026, 7, 20, 15, 0),
        quality_status="VALID",
    )
    rights = _rights_action(rights_ratio=0.3, subscription_price=6.0)
    result = CorporateActionAdjuster.adjust(DATES, raw, [bonus, rights], AS_OF_LATE)

    f_bonus = 1.0 / (1.0 + 0.2)
    f_rights = (90.0 + 0.3 * 6.0) / (90.0 * 1.3)
    expected = f_bonus * f_rights
    assert result.adj_factors[0] == pytest.approx(expected)
    assert result.adj_factors[1] == pytest.approx(expected)
    assert result.adj_factors[2] == pytest.approx(1.0)
    assert set(result.actions_applied) == {"BONUS_ISSUE:2026-08-04", "RIGHTS_OFFERING:2026-08-04"}


# --- TEST I: Corporate Action PIT `received_at` Hardening --------------------------------------
#
# Prior to this hardening, PITGate.filter_pit_corporate_actions() and CorporateActionStore's
# query_pit()/query_pit_range() checked available_at only. Both now also require
# received_at <= as_of, matching the already-established dual-cutoff pattern used by
# filter_pit_fundamentals() (pit_gate.py) and RevisionStore.query_pit() (revision_store.py) for
# other data types.

PIT_CUTOFF = datetime(2026, 8, 5, 12, 0)


def _pit_action(available_at, received_at, action_type="STOCK_SPLIT"):
    return CorporateActionContract(
        symbol="600519.SH", ex_date="2026-08-04", action_type=action_type,
        cash_amount_per_share=0.0, bonus_ratio=0.0, split_ratio=2.0,
        announcement_date="2026-07-20", available_at=available_at, received_at=received_at,
        quality_status="VALID",
    )


# -- PITGate.filter_pit_corporate_actions() -------------------------------------------------

def test_pit_corporate_action_normal_visible_when_both_cutoffs_satisfied():
    action = _pit_action(available_at=datetime(2026, 8, 1), received_at=datetime(2026, 8, 2))
    assert PITGate.filter_pit_corporate_actions([action], PIT_CUTOFF) == [action]


def test_pit_corporate_action_excluded_when_available_at_after_cutoff():
    action = _pit_action(available_at=datetime(2026, 8, 6), received_at=datetime(2026, 8, 2))
    assert PITGate.filter_pit_corporate_actions([action], PIT_CUTOFF) == []


def test_pit_corporate_action_excluded_when_received_at_after_cutoff():
    """The core of this hardening: before this change, this action would have been (incorrectly)
    visible, because filter_pit_corporate_actions() checked available_at only."""
    action = _pit_action(available_at=datetime(2026, 8, 1), received_at=datetime(2026, 8, 6))
    assert PITGate.filter_pit_corporate_actions([action], PIT_CUTOFF) == []


def test_pit_corporate_action_excluded_when_both_cutoffs_violated():
    action = _pit_action(available_at=datetime(2026, 8, 6), received_at=datetime(2026, 8, 7))
    assert PITGate.filter_pit_corporate_actions([action], PIT_CUTOFF) == []


def test_pit_corporate_action_visible_at_exact_cutoff_equality():
    action = _pit_action(available_at=PIT_CUTOFF, received_at=PIT_CUTOFF)
    assert PITGate.filter_pit_corporate_actions([action], PIT_CUTOFF) == [action]


def test_pit_corporate_action_missing_received_at_excluded_fails_closed():
    """received_at is a required (non-Optional) field on CorporateActionContract, but nothing
    prevents a caller from passing None at runtime (Python dataclasses don't enforce type hints
    at construction time). An unset received_at must be excluded, never treated as
    always-visible — the same fail-closed rule filter_pit_fundamentals() already applies."""
    action = _pit_action(available_at=datetime(2026, 8, 1), received_at=None)
    assert PITGate.filter_pit_corporate_actions([action], PIT_CUTOFF) == []


# -- CorporateActionStore.query_pit() / query_pit_range() ------------------------------------

def test_store_query_pit_normal_visible_when_both_cutoffs_satisfied():
    store = CorporateActionStore()
    action = _pit_action(available_at=datetime(2026, 8, 1), received_at=datetime(2026, 8, 2))
    store.add_action(action)
    assert store.query_pit("600519.SH", "2026-08-04", "STOCK_SPLIT", PIT_CUTOFF) == action


def test_store_query_pit_excluded_when_received_at_after_cutoff():
    store = CorporateActionStore()
    action = _pit_action(available_at=datetime(2026, 8, 1), received_at=datetime(2026, 8, 6))
    store.add_action(action)
    assert store.query_pit("600519.SH", "2026-08-04", "STOCK_SPLIT", PIT_CUTOFF) is None


def test_store_query_pit_falls_back_to_earlier_revision_when_latest_received_late():
    """Revision-selection correctness: a later, corrected revision whose received_at hasn't
    arrived yet as of the cutoff must NOT shadow an earlier revision that IS fully visible
    (both available_at and received_at <= as_of) — the store must select the earlier revision,
    not silently return None for the whole action."""
    store = CorporateActionStore()
    original = _pit_action(available_at=datetime(2026, 7, 20), received_at=datetime(2026, 7, 20))
    corrected = _pit_action(available_at=datetime(2026, 8, 1), received_at=datetime(2026, 8, 20))
    store.add_action(original)
    store.add_action(corrected)

    result = store.query_pit("600519.SH", "2026-08-04", "STOCK_SPLIT", PIT_CUTOFF)
    assert result == original, "must fall back to the fully-visible earlier revision, not return None"


def test_store_query_pit_range_excludes_action_with_late_received_at():
    store = CorporateActionStore()
    action = _pit_action(available_at=datetime(2026, 8, 1), received_at=datetime(2026, 8, 6))
    store.add_action(action)
    results = store.query_pit_range("600519.SH", "2026-08-01", "2026-08-06", PIT_CUTOFF)
    assert results == []


# -- CorporateActionAdjuster.adjust() (same PITGate path, exercised via the full adjuster) ---

def test_adjust_excludes_action_with_late_received_at():
    raw = [100.0, 100.0, 50.0, 50.0, 50.0]
    late_received = _pit_action(available_at=datetime(2026, 7, 20), received_at=datetime(2026, 8, 9))
    result = CorporateActionAdjuster.adjust(DATES, raw, [late_received], PIT_CUTOFF)
    assert result.adjusted_prices == raw
    assert result.actions_applied == []


# --- TEST K: Corporate Action Unified Formula (algorithm_version 1.0/2.0) ----------------------
#
# CORPORATE_ACTION_UNIFIED_FORMULA_ARCHITECTURE_PROPOSAL.md (CEO-approved). All expected values
# below are P_ex/P_pre computed independently from docs/CORPORATE_ACTION_SPECIFICATION.md's
# formula: P_ex = (P_pre - D + Pr*R) / (1 + B + R). Fixture: raw = [100.0, 100.0, 90.0, 90.0,
# 90.0], so P_pre = raw[1] = 100.0 and the legacy reference_price = raw[2] = 90.0 — deliberately
# different, so a "1.0" vs "2.0" test using the wrong price basis would fail, not accidentally pass.

RAW_UNIFIED = [100.0, 100.0, 90.0, 90.0, 90.0]
P_PRE = RAW_UNIFIED[1]


def _bonus_action(bonus_ratio=0.2, available_at=datetime(2026, 7, 20, 15, 0)):
    return CorporateActionContract(
        symbol="600519.SH", ex_date="2026-08-04", action_type="BONUS_ISSUE",
        cash_amount_per_share=0.0, bonus_ratio=bonus_ratio, split_ratio=1.0,
        announcement_date="2026-07-20", available_at=available_at, received_at=available_at,
        quality_status="VALID",
    )


def test_unified_dividend_only_uses_p_pre():
    result = CorporateActionAdjuster.adjust(
        DATES, RAW_UNIFIED, [_dividend_action()], AS_OF_LATE, algorithm_version="2.0"
    )
    expected = (P_PRE - 10.0) / P_PRE
    assert result.adj_factors[0] == pytest.approx(expected)


def test_unified_bonus_only_byte_identical_both_versions():
    """BONUS_ISSUE has no price dependency — must be identical under "1.0" and "2.0"."""
    f1 = CorporateActionAdjuster.adjust(DATES, RAW_UNIFIED, [_bonus_action()], AS_OF_LATE, algorithm_version="1.0").adj_factors[0]
    f2 = CorporateActionAdjuster.adjust(DATES, RAW_UNIFIED, [_bonus_action()], AS_OF_LATE, algorithm_version="2.0").adj_factors[0]
    assert f1 == f2 == pytest.approx(1.0 / 1.2)


def test_unified_rights_only_uses_p_pre():
    result = CorporateActionAdjuster.adjust(
        DATES, RAW_UNIFIED, [_rights_action(rights_ratio=0.3, subscription_price=6.0)],
        AS_OF_LATE, algorithm_version="2.0",
    )
    expected = (P_PRE + 0.3 * 6.0) / (P_PRE * 1.3)
    assert result.adj_factors[0] == pytest.approx(expected)


def test_unified_dividend_plus_bonus_matches_unified_formula():
    result = CorporateActionAdjuster.adjust(
        DATES, RAW_UNIFIED, [_dividend_action(), _bonus_action()], AS_OF_LATE, algorithm_version="2.0",
    )
    expected = (P_PRE - 10.0) / (1.0 + 0.2) / P_PRE
    assert result.adj_factors[0] == pytest.approx(expected)


def test_unified_dividend_plus_rights_matches_unified_formula():
    result = CorporateActionAdjuster.adjust(
        DATES, RAW_UNIFIED, [_dividend_action(), _rights_action(rights_ratio=0.3, subscription_price=6.0)],
        AS_OF_LATE, algorithm_version="2.0",
    )
    expected = (P_PRE - 10.0 + 6.0 * 0.3) / (1.0 + 0.3) / P_PRE
    assert result.adj_factors[0] == pytest.approx(expected)


def test_unified_bonus_plus_rights_matches_unified_formula():
    result = CorporateActionAdjuster.adjust(
        DATES, RAW_UNIFIED, [_bonus_action(), _rights_action(rights_ratio=0.3, subscription_price=6.0)],
        AS_OF_LATE, algorithm_version="2.0",
    )
    expected = (P_PRE + 6.0 * 0.3) / (1.0 + 0.2 + 0.3) / P_PRE
    assert result.adj_factors[0] == pytest.approx(expected)


def test_unified_dividend_plus_bonus_plus_rights_matches_unified_formula():
    result = CorporateActionAdjuster.adjust(
        DATES, RAW_UNIFIED,
        [_dividend_action(), _bonus_action(), _rights_action(rights_ratio=0.3, subscription_price=6.0)],
        AS_OF_LATE, algorithm_version="2.0",
    )
    expected = (P_PRE - 10.0 + 6.0 * 0.3) / (1.0 + 0.2 + 0.3) / P_PRE
    assert result.adj_factors[0] == pytest.approx(expected)


def test_unified_combined_factor_fails_closed_on_non_positive_ex_price():
    """A dividend large enough (relative to P_pre and the rights term) to drive the unified
    numerator non-positive must fail closed, mirroring CASH_DIVIDEND's existing D >= P rule."""
    huge_dividend = CorporateActionContract(
        symbol="600519.SH", ex_date="2026-08-04", action_type="CASH_DIVIDEND",
        cash_amount_per_share=200.0, bonus_ratio=0.0, split_ratio=1.0,
        announcement_date="2026-07-20", available_at=datetime(2026, 7, 20), received_at=datetime(2026, 7, 20),
        quality_status="VALID",
    )
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CorporateActionAdjuster.adjust(
            DATES, RAW_UNIFIED, [huge_dividend, _rights_action(rights_ratio=0.3, subscription_price=6.0)],
            AS_OF_LATE, algorithm_version="2.0",
        )


# -- STOCK_SPLIT scope boundary: never folded into the unified D/B/R computation ---------------

def test_unified_stock_split_only_byte_identical_both_versions():
    raw = [100.0, 100.0, 50.0, 50.0, 50.0]
    f1 = CorporateActionAdjuster.adjust(DATES, raw, [_split_action()], AS_OF_LATE, algorithm_version="1.0").adj_factors[0]
    f2 = CorporateActionAdjuster.adjust(DATES, raw, [_split_action()], AS_OF_LATE, algorithm_version="2.0").adj_factors[0]
    assert f1 == f2 == pytest.approx(0.5)


def test_unified_rights_plus_split_applies_split_independently_not_in_unified_formula():
    """rights+split must equal unified_D0_B0_R(P_pre) * (1/split_ratio) — proving STOCK_SPLIT's
    factor is multiplied on top, never passed into _combined_dbr_factor (§3.2 of the proposal)."""
    result = CorporateActionAdjuster.adjust(
        DATES, RAW_UNIFIED, [_rights_action(rights_ratio=0.3, subscription_price=6.0), _split_action()],
        AS_OF_LATE, algorithm_version="2.0",
    )
    rights_only_factor = (P_PRE + 6.0 * 0.3) / (P_PRE * 1.3)
    expected = rights_only_factor * (1.0 / 2.0)
    assert result.adj_factors[0] == pytest.approx(expected)
    assert set(result.actions_applied) == {"RIGHTS_OFFERING:2026-08-04", "STOCK_SPLIT:2026-08-04"}


def test_unified_dividend_bonus_rights_split_all_four_scope_boundary():
    result = CorporateActionAdjuster.adjust(
        DATES, RAW_UNIFIED,
        [_dividend_action(), _bonus_action(), _rights_action(rights_ratio=0.3, subscription_price=6.0), _split_action()],
        AS_OF_LATE, algorithm_version="2.0",
    )
    dbr_factor = (P_PRE - 10.0 + 6.0 * 0.3) / (1.0 + 0.2 + 0.3) / P_PRE
    expected = dbr_factor * (1.0 / 2.0)
    assert result.adj_factors[0] == pytest.approx(expected)


# -- algorithm_version handling ------------------------------------------------------------------

def test_adjust_defaults_to_legacy_algorithm_version():
    """No algorithm_version supplied must behave exactly like an explicit "1.0" — proves the
    default preserves pre-existing behavior for call sites that predate versioning."""
    explicit = CorporateActionAdjuster.adjust(
        DATES, RAW_UNIFIED, [_dividend_action()], AS_OF_LATE, algorithm_version="1.0"
    )
    implicit = CorporateActionAdjuster.adjust(DATES, RAW_UNIFIED, [_dividend_action()], AS_OF_LATE)
    assert implicit.adj_factors == explicit.adj_factors
    assert implicit.adjusted_prices == explicit.adjusted_prices


def test_adjust_invalid_algorithm_version_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CorporateActionAdjuster.adjust(
            DATES, RAW_UNIFIED, [_dividend_action()], AS_OF_LATE, algorithm_version="3.0"
        )
