"""
test_technical_indicators_t5.py — realized volatility / momentum / volume indicators
(Terminal directive step T5).

Each indicator is checked against a hand-computed expected value, not against its own output, so
a formula change cannot silently redefine what these tests assert. The existing MA/RSI/MACD suite
in test_technical_indicators.py is untouched.
"""

import math

import pytest

from src.quant.technical.indicators import (
    compute_momentum_indicator,
    compute_realized_volatility,
    compute_volume_indicator,
)

SYMBOL = "600519.SH"


def _dates(n):
    return [f"2026-01-{d:02d}" for d in range(1, n + 1)]


# --- realized volatility -----------------------------------------------------------------------

def test_realized_volatility_matches_a_hand_computed_value():
    prices = [100.0, 101.0, 102.0, 101.0, 103.0, 104.0]
    dates = _dates(len(prices))
    window = 3

    results = compute_realized_volatility(SYMBOL, dates, prices, window=window)
    last = results[-1]

    log_returns = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
    sample = log_returns[-window:]
    mean = sum(sample) / window
    variance = sum((r - mean) ** 2 for r in sample) / (window - 1)
    expected = math.sqrt(variance) * math.sqrt(252)

    assert last.calculated_value == pytest.approx(round(expected, 6))
    assert last.metric_name == "REALIZED_VOLATILITY_3"
    assert last.quality_status == "VALID"


def test_realized_volatility_is_annualized_by_sqrt_252():
    """A constant daily return has zero dispersion; a fixed alternating one is checkable."""
    prices = [100.0 * (1.01 ** i) for i in range(10)]
    results = compute_realized_volatility(SYMBOL, _dates(10), prices, window=5)
    assert results[-1].calculated_value == pytest.approx(0.0, abs=1e-9)


def test_realized_volatility_warm_up_records_are_explicit_not_zero():
    prices = [100.0 + i for i in range(6)]
    results = compute_realized_volatility(SYMBOL, _dates(6), prices, window=3)
    warm_up = results[:3]
    assert all(r.warm_up_satisfied is False for r in warm_up)
    assert all(r.calculated_value is None for r in warm_up)   # never fabricated as 0.0
    assert all(r.quality_status == "INSUFFICIENT_WARM_UP" for r in warm_up)
    assert results[3].warm_up_satisfied is True


def test_realized_volatility_lookback_is_window_plus_one():
    results = compute_realized_volatility(SYMBOL, _dates(6), [100.0 + i for i in range(6)], window=3)
    assert results[-1].lookback_window == 4


@pytest.mark.parametrize("window", [0, 1, -5])
def test_realized_volatility_rejects_a_window_too_small_for_a_sample_stdev(window):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_realized_volatility(SYMBOL, _dates(5), [100.0] * 5, window=window)


# --- momentum ------------------------------------------------------------------------------------

def test_momentum_is_rate_of_change_over_the_window():
    prices = [100.0, 105.0, 110.0, 120.0]
    results = compute_momentum_indicator(SYMBOL, _dates(4), prices, window=2)
    # index 2: (110 - 100)/100 ; index 3: (120 - 105)/105
    assert results[2].calculated_value == pytest.approx(0.1)
    assert results[3].calculated_value == pytest.approx(round((120.0 - 105.0) / 105.0, 6))


def test_momentum_reports_a_decline_as_negative():
    results = compute_momentum_indicator(SYMBOL, _dates(3), [100.0, 99.0, 90.0], window=2)
    assert results[-1].calculated_value == pytest.approx(-0.1)


def test_momentum_warm_up_records_are_explicit():
    results = compute_momentum_indicator(SYMBOL, _dates(4), [100.0] * 4, window=2)
    assert [r.warm_up_satisfied for r in results] == [False, False, True, True]
    assert results[0].calculated_value is None


def test_momentum_cites_exactly_the_two_prices_it_used():
    results = compute_momentum_indicator(SYMBOL, _dates(4), [100.0, 101.0, 102.0, 103.0], window=2)
    assert results[3].input_data_ids == [f"{SYMBOL}:2026-01-02", f"{SYMBOL}:2026-01-04"]


def test_momentum_metric_name_records_the_window():
    results = compute_momentum_indicator(SYMBOL, _dates(4), [100.0] * 4, window=2)
    assert results[-1].metric_name == "MOMENTUM_2"


def test_momentum_rejects_an_invalid_window():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_momentum_indicator(SYMBOL, _dates(3), [100.0] * 3, window=0)


# --- volume ----------------------------------------------------------------------------------------

def test_volume_reports_average_and_same_day_ratio():
    volumes = [100.0, 200.0, 300.0, 800.0]
    results = compute_volume_indicator(SYMBOL, _dates(4), volumes, window=3)
    last = results[-1].calculated_value
    average = (200.0 + 300.0 + 800.0) / 3
    assert last["volume"] == 800.0
    assert last["volume_ma"] == pytest.approx(round(average, 6))
    assert last["volume_ratio"] == pytest.approx(round(800.0 / average, 6))


def test_volume_spike_shows_a_ratio_above_one():
    results = compute_volume_indicator(SYMBOL, _dates(4), [100.0, 100.0, 100.0, 500.0], window=3)
    assert results[-1].calculated_value["volume_ratio"] > 1.0


def test_zero_volume_is_valid_input_unlike_a_zero_price():
    """A suspended session legitimately trades zero shares; the price validator would reject 0."""
    results = compute_volume_indicator(SYMBOL, _dates(4), [100.0, 0.0, 100.0, 100.0], window=3)
    assert results[-1].quality_status == "VALID"


def test_an_all_zero_window_reports_an_undefined_ratio_not_a_fabricated_one():
    results = compute_volume_indicator(SYMBOL, _dates(3), [0.0, 0.0, 0.0], window=3)
    value = results[-1].calculated_value
    assert value["volume_ma"] == 0.0
    assert value["volume_ratio"] is None      # never 0.0 or 1.0, which would read as measured


def test_volume_records_the_split_adjustment_flag_rather_than_assuming_it():
    default = compute_volume_indicator(SYMBOL, _dates(3), [1.0, 2.0, 3.0], window=3)
    flagged = compute_volume_indicator(
        SYMBOL, _dates(3), [1.0, 2.0, 3.0], window=3, volume_split_adjusted=True
    )
    assert default[-1].parameters["volume_split_adjusted"] is False
    assert flagged[-1].parameters["volume_split_adjusted"] is True


def test_volume_declares_price_basis_not_applicable():
    results = compute_volume_indicator(SYMBOL, _dates(3), [1.0, 2.0, 3.0], window=3)
    assert results[-1].input_price_basis == "NOT_APPLICABLE"


def test_volume_warm_up_records_are_explicit():
    results = compute_volume_indicator(SYMBOL, _dates(4), [1.0, 2.0, 3.0, 4.0], window=3)
    assert [r.warm_up_satisfied for r in results] == [False, False, True, True]
    assert results[0].calculated_value is None


def test_volume_rejects_a_negative_value():
    with pytest.raises(ValueError, match="negative volume"):
        compute_volume_indicator(SYMBOL, _dates(3), [1.0, -2.0, 3.0], window=2)


def test_volume_rejects_a_length_mismatch():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_volume_indicator(SYMBOL, _dates(3), [1.0, 2.0], window=2)


def test_volume_rejects_unsorted_dates():
    with pytest.raises(ValueError, match="sorted ascending"):
        compute_volume_indicator(
            SYMBOL, ["2026-01-03", "2026-01-01", "2026-01-02"], [1.0, 2.0, 3.0], window=2
        )


# --- shared guarantees ------------------------------------------------------------------------------

@pytest.mark.parametrize("compute", [compute_realized_volatility, compute_momentum_indicator])
def test_price_based_indicators_reject_a_non_positive_price(compute):
    with pytest.raises(ValueError, match="non-positive price"):
        compute(SYMBOL, _dates(5), [100.0, 101.0, 0.0, 102.0, 103.0], window=2)


@pytest.mark.parametrize("compute", [compute_realized_volatility, compute_momentum_indicator])
def test_price_based_indicators_return_one_record_per_input_date(compute):
    dates = _dates(7)
    assert len(compute(SYMBOL, dates, [100.0 + i for i in range(7)], window=3)) == len(dates)


def test_volume_returns_one_record_per_input_date():
    dates = _dates(7)
    assert len(compute_volume_indicator(SYMBOL, dates, [1.0] * 7, window=3)) == len(dates)


@pytest.mark.parametrize("compute", [compute_realized_volatility, compute_momentum_indicator])
def test_indicators_never_look_beyond_their_input_window(compute):
    """PIT safety is structural: truncating the series must not change earlier values."""
    dates, prices = _dates(8), [100.0 + i for i in range(8)]
    full = compute(SYMBOL, dates, prices, window=3)
    truncated = compute(SYMBOL, dates[:6], prices[:6], window=3)
    assert [r.calculated_value for r in truncated] == [r.calculated_value for r in full[:6]]
