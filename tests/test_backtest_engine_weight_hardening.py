"""
test_backtest_engine_weight_hardening.py — Phase 8A prerequisite hardening (Directive
CEO-2026-08-03-RESEARCH-008A-HARDEN-BACKTEST §4).

REGRESSION TEST FOR A REAL, PREVIOUSLY-UNDETECTED BUG:

OLD BEHAVIOR: BacktestEngine.run_backtest computed daily_return as an unweighted average
across every symbol in daily_prices, completely ignoring PortfolioTarget.weights. A 100%-long
portfolio and its exact opposite (100% long the other side) produced IDENTICAL results.

NEW BEHAVIOR: daily_return is the weights-weighted sum of each held symbol's return. Weights
are long-only (no shorts) and non-leveraged (sum <= 1.0); a symbol in weights but absent from
daily_prices, a negative weight, or weights summing over 1.0 all fail closed. Exactly one
PortfolioTarget is required per call — multi-period rebalancing within one call is not a
defined semantic anywhere in this codebase and is not guessed at here.
"""

import pytest

from src.quant.backtest.engine import BacktestEngine
from src.quant.portfolio.construction import PortfolioTarget

PRICES = {
    "A": [100.0, 110.0, 121.0],   # up ~10% each day
    "B": [100.0, 90.0, 81.0],     # down ~10% each day
}


def _run(weights):
    engine = BacktestEngine()
    targets = [PortfolioTarget("2026-08-01", "strat_test", weights, sum(weights.values()))]
    return engine.run_backtest("ds_test", "strat_test", PRICES, targets)


# --- TEST A: same prices + different weights -> different result ----------------------------

def test_a_different_weights_produce_different_results():
    r1 = _run({"A": 1.0, "B": 0.0})
    r2 = _run({"A": 0.0, "B": 1.0})
    assert r1.total_return != r2.total_return


# --- TEST B: 100% A vs 100% B -> result follows each asset's real performance ----------------

def test_b_result_direction_follows_held_asset_performance():
    r_a = _run({"A": 1.0, "B": 0.0})
    r_b = _run({"B": 1.0, "A": 0.0})
    assert r_a.total_return > 0, "100% long the rising asset must show positive return"
    assert r_b.total_return < 0, "100% long the falling asset must show negative return"


# --- TEST C: 50/50 portfolio -> lies between the two assets' standalone performance ----------

def test_c_mixed_portfolio_lies_between_the_two_assets():
    r_a = _run({"A": 1.0, "B": 0.0})
    r_b = _run({"B": 1.0, "A": 0.0})
    r_mixed = _run({"A": 0.5, "B": 0.5})
    lo, hi = sorted([r_a.total_return, r_b.total_return])
    assert lo <= r_mixed.total_return <= hi


# --- TEST D: zero-weight / unheld security does not contribute to portfolio return -----------

def test_d_zero_weight_security_does_not_affect_return():
    r_explicit_zero = _run({"A": 1.0, "B": 0.0})
    r_omitted = _run({"A": 1.0})  # B simply absent from weights, not explicitly zeroed
    assert r_explicit_zero.total_return == r_omitted.total_return


def test_d_extra_unweighted_symbol_in_daily_prices_is_ignored():
    """A universe of candidate symbols wider than what's actually held must not change the
    result — this is normal portfolio construction (holding 1 of N candidates), not an error."""
    engine = BacktestEngine()
    wide_prices = dict(PRICES)
    wide_prices["C"] = [50.0, 49.0, 48.0]  # present in daily_prices, never referenced in weights
    targets = [PortfolioTarget("2026-08-01", "strat_test", {"A": 1.0}, 1.0)]
    r_wide = engine.run_backtest("ds_test", "strat_test", wide_prices, targets)
    r_narrow = _run({"A": 1.0})
    assert r_wide.total_return == r_narrow.total_return


def test_d_fully_cash_empty_weights_is_a_valid_zero_return_result_not_a_failure():
    """An explicitly empty weights dict (e.g. a strategy with zero candidates today) is a
    valid, fully-cash portfolio — not an error — matching PortfolioConstructor's existing
    behavior of returning an empty PortfolioTarget when there are no BUY-biased candidates."""
    r = _run({})
    assert all(ret == 0.0 for ret in r.daily_returns)


# --- TEST E: portfolio_targets missing / cannot determine valid weights -> FAIL CLOSED -------

def test_e_empty_portfolio_targets_list_fails_closed():
    engine = BacktestEngine()
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        engine.run_backtest("ds_test", "strat_test", PRICES, [])


def test_e_none_portfolio_targets_fails_closed():
    engine = BacktestEngine()
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        engine.run_backtest("ds_test", "strat_test", PRICES, None)


def test_e_multiple_portfolio_targets_fails_closed():
    """Multi-period rebalancing across several targets in one call is not a defined semantic
    anywhere in this codebase (no caller has ever exercised it) — fail closed rather than
    silently picking one and guessing at a financial semantic that was never specified."""
    engine = BacktestEngine()
    targets = [
        PortfolioTarget("2026-08-01", "strat_test", {"A": 1.0}, 1.0),
        PortfolioTarget("2026-08-02", "strat_test", {"B": 1.0}, 1.0),
    ]
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        engine.run_backtest("ds_test", "strat_test", PRICES, targets)


def test_e_empty_daily_prices_fails_closed():
    engine = BacktestEngine()
    targets = [PortfolioTarget("2026-08-01", "strat_test", {"A": 1.0}, 1.0)]
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        engine.run_backtest("ds_test", "strat_test", {}, targets)


# --- TEST F: invalid weights -> FAIL CLOSED ---------------------------------------------------

def test_f_unknown_symbol_in_weights_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _run({"A": 0.5, "NONEXISTENT.SH": 0.5})


def test_f_negative_weight_fails_closed():
    """Short positions are not a supported financial semantic anywhere in this codebase (no
    short-selling infrastructure, cost model, or borrow-cost concept exists) — a negative
    weight fails closed rather than being silently interpreted as a short."""
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _run({"A": 1.5, "B": -0.5})


def test_f_weight_sum_exceeding_one_fails_closed():
    """Leverage (weights summing above 1.0) is not a supported semantic — fails closed rather
    than being silently clamped or renormalized inside the engine (renormalization, if wanted,
    is PortfolioConstructor's explicit, visible responsibility upstream — not a silent engine
    behavior)."""
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _run({"A": 0.8, "B": 0.8})


def test_f_weight_sum_less_than_one_is_valid_partial_investment():
    """Sanity check that TEST F's leverage rejection isn't accidentally rejecting the valid
    case of partial investment (sum < 1.0, rest implicit cash)."""
    r = _run({"A": 0.5})
    assert r.total_return != 0.0
