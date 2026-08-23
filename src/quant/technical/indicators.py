"""
indicators.py — Canonical Technical Indicator Calculation.

AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §5 (CEO-approved design), now implemented for
MA, RSI, and MACD only — per the CEO's explicit Step 5 instruction, this is honestly disclosed:
volatility/momentum/volume indicators are contract-designed (see the stub functions below, each
documenting input/formula/lookback) but NOT implemented in this phase. Do not treat their
presence as "done" — every one of them raises NotImplementedError.

Do not trust a third-party API's own reported indicator value (directive item 5) — every value
here is computed locally from a PIT-adjusted price series the caller supplies, never fetched.
If a live indicator API is ever integrated later, its values must be cross-validated against
these canonical calculations, not substituted for them.

Every function:
- Takes `dates: List[str]` (ascending) and `prices: List[float]` aligned 1:1 — the SAME shape
  CorporateActionAdjuster.adjust() already produces (`adjusted_prices`), so PIT-safety is
  inherited structurally: these functions never look beyond the input list's own bounds, so if
  the caller has already PIT-truncated `dates`/`prices` to `as_of`, every returned value is
  automatically PIT-safe too — no separate PIT gate is needed for locally-computed indicators
  (see the architecture proposal's §4 rationale for why this differs from News, where a real
  external-provider latency dimension exists and a PITGate method is warranted).
- Returns one DerivedDataContract per input date — dates without enough warm-up history get an
  explicit `warm_up_satisfied=False`, `quality_status="INSUFFICIENT_WARM_UP"`, `calculated_value
  =None` record, never silently omitted and never fabricated as 0.0.
- Fails closed (raises ValueError) on malformed input (non-positive price, NaN, length mismatch,
  unordered dates) — a malformed INPUT is a data-integrity problem, distinct from "insufficient
  history," and must not be silently skipped either.
"""

import math
from datetime import datetime
from typing import List

from src.data.contracts.derived import DerivedDataContract

FORMULA_VERSION = "1.0"
LOCAL_CALCULATION_SOURCE = "LOCAL_CANONICAL_CALCULATION"


def _validate_series(dates: List[str], prices: List[float]) -> None:
    if len(dates) != len(prices):
        raise ValueError("FAIL CLOSED: dates and prices length mismatch.")
    if dates != sorted(dates):
        raise ValueError("FAIL CLOSED: dates must be sorted ascending.")
    for p in prices:
        if p is None or (isinstance(p, float) and math.isnan(p)):
            raise ValueError("FAIL CLOSED: price series contains a None/NaN value.")
        if p <= 0:
            raise ValueError(f"FAIL CLOSED: non-positive price {p} in input series.")


def _warm_up_record(symbol, dates, i, metric_name, parameters, lookback_window, input_price_basis, data_origin):
    return DerivedDataContract(
        symbol=symbol, metric_name=metric_name, calculated_value=None,
        derived_at=datetime.now(), formula_version=FORMULA_VERSION,
        input_data_ids=[f"{symbol}:{dates[i]}"], input_as_of=datetime.now(),
        quality_status="INSUFFICIENT_WARM_UP",
        effective_date=dates[i], parameters=parameters, input_price_basis=input_price_basis,
        lookback_window=lookback_window, warm_up_satisfied=False, data_origin=data_origin,
    )


def compute_moving_average(
    symbol: str, dates: List[str], prices: List[float], window: int = 20,
    input_price_basis: str = "PIT_ADJUSTED", data_origin: str = "SYNTHETIC_DATA",
) -> List[DerivedDataContract]:
    """MA_window[i] = mean(prices[i-window+1 : i+1]). Simple (unweighted) moving average.
    Warm-up: requires `window` prior prices (i >= window-1)."""
    if window <= 0:
        raise ValueError(f"FAIL CLOSED: invalid MA window {window}.")
    _validate_series(dates, prices)
    params = {"window": window}
    results = []
    for i in range(len(dates)):
        if i < window - 1:
            results.append(_warm_up_record(symbol, dates, i, f"MA_{window}", params, window, input_price_basis, data_origin))
            continue
        value = sum(prices[i - window + 1: i + 1]) / window
        results.append(DerivedDataContract(
            symbol=symbol, metric_name=f"MA_{window}", calculated_value=round(value, 6),
            derived_at=datetime.now(), formula_version=FORMULA_VERSION,
            input_data_ids=[f"{symbol}:{d}" for d in dates[i - window + 1: i + 1]],
            input_as_of=datetime.now(), quality_status="VALID",
            effective_date=dates[i], parameters=params, input_price_basis=input_price_basis,
            lookback_window=window, warm_up_satisfied=True, data_origin=data_origin,
        ))
    return results


def compute_rsi(
    symbol: str, dates: List[str], prices: List[float], window: int = 14,
    input_price_basis: str = "PIT_ADJUSTED", data_origin: str = "SYNTHETIC_DATA",
) -> List[DerivedDataContract]:
    """Simple-average RSI (not Wilder-smoothed — a deliberate, documented choice; Wilder
    smoothing is a different, unimplemented variant, not silently substituted).
    delta[t] = prices[t] - prices[t-1] for t=1..n-1. avg_gain/avg_loss = mean of
    positive/negative deltas over the trailing `window` deltas ending at i. RS = avg_gain /
    avg_loss; RSI = 100 - 100/(1+RS). RSI=100 if avg_loss==0 and avg_gain>0; RSI=50 (neutral,
    documented convention) if both are 0. Warm-up: requires `window` deltas (i >= window)."""
    if window <= 0:
        raise ValueError(f"FAIL CLOSED: invalid RSI window {window}.")
    _validate_series(dates, prices)
    params = {"window": window}
    deltas = [prices[t] - prices[t - 1] for t in range(1, len(prices))]  # deltas[t-1] = delta at index t
    results = []
    for i in range(len(dates)):
        if i < window:
            results.append(_warm_up_record(symbol, dates, i, f"RSI_{window}", params, window, input_price_basis, data_origin))
            continue
        window_deltas = deltas[i - window: i]  # deltas for t = i-window+1 .. i
        gains = [d for d in window_deltas if d > 0]
        losses = [-d for d in window_deltas if d < 0]
        avg_gain = sum(gains) / window
        avg_loss = sum(losses) / window
        if avg_loss == 0 and avg_gain == 0:
            rsi = 50.0
        elif avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        results.append(DerivedDataContract(
            symbol=symbol, metric_name=f"RSI_{window}", calculated_value=round(rsi, 6),
            derived_at=datetime.now(), formula_version=FORMULA_VERSION,
            input_data_ids=[f"{symbol}:{d}" for d in dates[i - window: i + 1]],
            input_as_of=datetime.now(), quality_status="VALID",
            effective_date=dates[i], parameters=params, input_price_basis=input_price_basis,
            lookback_window=window, warm_up_satisfied=True, data_origin=data_origin,
        ))
    return results


def _ema_series(values: List[float], span: int) -> List[float]:
    """EMA seeded with the SMA of the first `span` values (a documented convention — an
    alternative "seed with first value" convention exists and is deliberately not used).
    Returns a list aligned to `values`, with entries before the seed index as None."""
    k = 2.0 / (span + 1.0)
    ema = [None] * len(values)
    if len(values) < span:
        return ema
    seed = sum(values[:span]) / span
    ema[span - 1] = seed
    for i in range(span, len(values)):
        ema[i] = values[i] * k + ema[i - 1] * (1.0 - k)
    return ema


def compute_macd(
    symbol: str, dates: List[str], prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9,
    input_price_basis: str = "PIT_ADJUSTED", data_origin: str = "SYNTHETIC_DATA",
) -> List[DerivedDataContract]:
    """MACD_line = EMA(prices, fast) - EMA(prices, slow). Signal_line = EMA(MACD_line, signal).
    Histogram = MACD_line - Signal_line. Both EMAs are SMA-seeded (see _ema_series). The whole
    indicator (all three components) is reported together, only once ALL THREE are available —
    a deliberate simplification over reporting a partial dict, to avoid ambiguity about which
    sub-fields are populated. Warm-up: requires slow + signal - 1 prior prices."""
    if fast <= 0 or slow <= 0 or signal <= 0:
        raise ValueError(f"FAIL CLOSED: invalid MACD parameters fast={fast} slow={slow} signal={signal}.")
    if fast >= slow:
        raise ValueError(f"FAIL CLOSED: MACD requires fast ({fast}) < slow ({slow}).")
    _validate_series(dates, prices)
    params = {"fast": fast, "slow": slow, "signal": signal}
    lookback = slow + signal - 1

    ema_fast = _ema_series(prices, fast)
    ema_slow = _ema_series(prices, slow)
    macd_line = [
        (ema_fast[i] - ema_slow[i]) if (ema_fast[i] is not None and ema_slow[i] is not None) else None
        for i in range(len(prices))
    ]
    # Signal line is the EMA of macd_line, computed only over macd_line's own defined region.
    macd_defined_from = slow - 1
    macd_tail = [v for v in macd_line[macd_defined_from:] if v is not None]
    signal_tail = _ema_series(macd_tail, signal)
    signal_line = [None] * len(prices)
    for j, val in enumerate(signal_tail):
        signal_line[macd_defined_from + j] = val

    results = []
    for i in range(len(dates)):
        if signal_line[i] is None:
            results.append(_warm_up_record(symbol, dates, i, "MACD_12_26_9", params, lookback, input_price_basis, data_origin))
            continue
        value = {
            "macd_line": round(macd_line[i], 6),
            "signal_line": round(signal_line[i], 6),
            "histogram": round(macd_line[i] - signal_line[i], 6),
        }
        results.append(DerivedDataContract(
            symbol=symbol, metric_name="MACD_12_26_9", calculated_value=value,
            derived_at=datetime.now(), formula_version=FORMULA_VERSION,
            input_data_ids=[f"{symbol}:{d}" for d in dates[i - lookback + 1: i + 1]],
            input_as_of=datetime.now(), quality_status="VALID",
            effective_date=dates[i], parameters=params, input_price_basis=input_price_basis,
            lookback_window=lookback, warm_up_satisfied=True, data_origin=data_origin,
        ))
    return results


# --- Contract-only (NOT implemented this phase) — honestly disclosed, per the CEO's explicit
# instruction not to "假装完成" (pretend completion). Each documents input/formula/lookback so
# the design exists even though the calculation does not. -------------------------------------

def compute_realized_volatility(symbol: str, dates: List[str], prices: List[float], window: int = 20):
    """DESIGN ONLY — NOT IMPLEMENTED. Input: PIT-adjusted daily prices. Formula: annualized
    standard deviation of daily log returns over the trailing `window` days, scaled by
    sqrt(252) (the same convention as the existing, unregistered RealizedVolatilityFactor in
    src/quant/factors/volatility.py — this function would reuse that math conceptually, not
    duplicate a second implementation, if built). Lookback: `window` + 1 prices (for `window`
    returns). Missing data: same INSUFFICIENT_WARM_UP convention as MA/RSI/MACD above."""
    raise NotImplementedError(
        "compute_realized_volatility is contract-designed only, not implemented in this phase — "
        "see this function's docstring for the intended design."
    )


def compute_momentum_indicator(symbol: str, dates: List[str], prices: List[float], window: int = 20):
    """DESIGN ONLY — NOT IMPLEMENTED. Input: PIT-adjusted daily prices. Formula: rate-of-change,
    (price[i] - price[i-window]) / price[i-window] — a raw technical descriptive statistic, NOT
    the same computation as FactorRegistry's "momentum_20d:v1" (which produces a cross-sectional
    z-score for signal generation, a different consumption context — this function would not
    reimplement or replace that factor). Lookback: `window` + 1 prices."""
    raise NotImplementedError(
        "compute_momentum_indicator is contract-designed only, not implemented in this phase — "
        "see this function's docstring for the intended design."
    )


def compute_volume_indicator(symbol: str, dates: List[str], volumes: List[float], window: int = 20):
    """DESIGN ONLY — NOT IMPLEMENTED. Input: daily trading volume (not price). Formula:
    volume moving average + a same-day volume-vs-average ratio (a standard "volume spike"
    descriptive statistic). Lookback: `window` prior volume observations. Missing data: same
    INSUFFICIENT_WARM_UP convention. Note: volume is not corporate-action price-adjusted, so
    input_price_basis is not applicable the same way — this would need its own explicit
    "split-adjusted volume: yes/no" flag if implemented."""
    raise NotImplementedError(
        "compute_volume_indicator is contract-designed only, not implemented in this phase — "
        "see this function's docstring for the intended design."
    )
