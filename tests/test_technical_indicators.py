"""
test_technical_indicators.py — Canonical Technical Indicator calculation tests.

Directive Step 5: MA, RSI, MACD must be verified with normal data, warm-up, missing data,
invalid input, and deterministic calculation. Also confirms volatility/momentum/volume
indicators are honestly NOT implemented (contract-only), per the directive's explicit
instruction not to "假装完成" (pretend completion).
"""

from datetime import datetime, timedelta

import pytest

from src.quant.technical.indicators import (
    compute_moving_average, compute_rsi, compute_macd,
    compute_realized_volatility, compute_momentum_indicator, compute_volume_indicator,
)

SYMBOL = "600519.SH"


def _dates(n):
    start = datetime(2026, 1, 1)
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


# --- MA -------------------------------------------------------------------------------------

def test_ma_normal_data_and_warmup():
    dates = _dates(10)
    prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]
    results = compute_moving_average(SYMBOL, dates, prices, window=5)
    assert len(results) == 10
    for i in range(4):
        assert results[i].warm_up_satisfied is False
        assert results[i].quality_status == "INSUFFICIENT_WARM_UP"
        assert results[i].calculated_value is None
    assert results[4].warm_up_satisfied is True
    assert results[4].calculated_value == pytest.approx(12.0)   # mean(10..14)
    assert results[9].calculated_value == pytest.approx(17.0)   # mean(15..19)
    assert results[4].effective_date == dates[4]
    assert results[4].input_price_basis == "PIT_ADJUSTED"
    assert results[4].lookback_window == 5


def test_ma_missing_data_fails_closed():
    dates = _dates(3)
    prices = [10.0, None, 12.0]
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_moving_average(SYMBOL, dates, prices, window=2)


def test_ma_invalid_input_non_positive_price_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_moving_average(SYMBOL, _dates(3), [10.0, -5.0, 12.0], window=2)


def test_ma_invalid_window_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_moving_average(SYMBOL, _dates(3), [10.0, 11.0, 12.0], window=0)


def test_ma_deterministic():
    dates = _dates(10)
    prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]
    r1 = [x.calculated_value for x in compute_moving_average(SYMBOL, dates, prices, window=5)]
    r2 = [x.calculated_value for x in compute_moving_average(SYMBOL, dates, prices, window=5)]
    assert r1 == r2


# --- RSI ------------------------------------------------------------------------------------

def test_rsi_normal_data_and_warmup():
    dates = _dates(20)
    prices = [100.0] * 20
    for i in range(1, 20):
        prices[i] = prices[i - 1] + (1.0 if i % 2 == 0 else -0.5)
    results = compute_rsi(SYMBOL, dates, prices, window=14)
    for i in range(14):
        assert results[i].warm_up_satisfied is False
        assert results[i].calculated_value is None
    assert results[14].warm_up_satisfied is True
    assert 0.0 <= results[14].calculated_value <= 100.0


def test_rsi_all_gains_yields_100():
    dates = _dates(16)
    prices = [100.0 + i for i in range(16)]  # monotonically increasing => all gains
    results = compute_rsi(SYMBOL, dates, prices, window=14)
    assert results[14].calculated_value == pytest.approx(100.0)


def test_rsi_no_movement_yields_50():
    dates = _dates(16)
    prices = [100.0] * 16  # flat series => no gains, no losses
    results = compute_rsi(SYMBOL, dates, prices, window=14)
    assert results[14].calculated_value == pytest.approx(50.0)


def test_rsi_missing_data_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_rsi(SYMBOL, _dates(3), [10.0, float("nan"), 12.0], window=2)


def test_rsi_invalid_input_length_mismatch_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_rsi(SYMBOL, _dates(3), [10.0, 11.0], window=2)


def test_rsi_deterministic():
    dates = _dates(20)
    prices = [100.0 + (i % 3) for i in range(20)]
    r1 = [x.calculated_value for x in compute_rsi(SYMBOL, dates, prices, window=14)]
    r2 = [x.calculated_value for x in compute_rsi(SYMBOL, dates, prices, window=14)]
    assert r1 == r2


# --- MACD -----------------------------------------------------------------------------------

def test_macd_normal_data_and_warmup():
    dates = _dates(40)
    prices = [100.0 + i * 0.5 for i in range(40)]
    results = compute_macd(SYMBOL, dates, prices, fast=12, slow=26, signal=9)
    first_valid = 26 + 9 - 2  # slow + signal - 2, verified by direct computation
    for i in range(first_valid):
        assert results[i].warm_up_satisfied is False
        assert results[i].calculated_value is None
    assert results[first_valid].warm_up_satisfied is True
    val = results[first_valid].calculated_value
    assert set(val.keys()) == {"macd_line", "signal_line", "histogram"}
    assert val["histogram"] == pytest.approx(val["macd_line"] - val["signal_line"])


def test_macd_invalid_parameters_fast_gte_slow_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_macd(SYMBOL, _dates(5), [1.0] * 5, fast=26, slow=12)


def test_macd_missing_data_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_macd(SYMBOL, _dates(5), [1.0, 2.0, None, 4.0, 5.0])


def test_macd_deterministic():
    dates = _dates(40)
    prices = [100.0 + i * 0.5 for i in range(40)]
    r1 = [x.calculated_value for x in compute_macd(SYMBOL, dates, prices)]
    r2 = [x.calculated_value for x in compute_macd(SYMBOL, dates, prices)]
    assert r1 == r2


# --- Honest incompleteness — NOT implemented this phase --------------------------------------

def test_volatility_momentum_volume_indicators_not_implemented_honestly():
    with pytest.raises(NotImplementedError):
        compute_realized_volatility(SYMBOL, _dates(5), [1.0] * 5)
    with pytest.raises(NotImplementedError):
        compute_momentum_indicator(SYMBOL, _dates(5), [1.0] * 5)
    with pytest.raises(NotImplementedError):
        compute_volume_indicator(SYMBOL, _dates(5), [1.0] * 5)
