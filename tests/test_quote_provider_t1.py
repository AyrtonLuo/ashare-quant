"""
test_quote_provider_t1.py — QuoteContract, QuoteProvider and DataTrustGate.validate_quote
(Terminal directive step T1).

The Terminal's central safety property is that a demo quote can never present itself as a live
one. These tests assert that structurally, not by inspecting UI strings.
"""

from datetime import datetime, timedelta

import pytest

from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.quote import QuoteContract
from src.data.providers.base import ProviderError
from src.data.providers.quote_provider import (
    NO_QUOTE_VENDOR_REASON,
    GoldenQuoteProvider,
    LiveQuoteProvider,
    QuoteProvider,
)
from src.data.validation.gate import DataTrustGate

SYMBOL = "600519.SH"
QUOTED_AT = datetime(2026, 8, 3, 14, 30, 0)


def _quote(**overrides):
    base = dict(
        symbol=SYMBOL, display_name="贵州茅台", last_price=105.0, prev_close=100.0,
        open_price=101.0, high_price=106.0, low_price=99.0, volume=1000.0, amount=105000.0,
        quoted_at=QUOTED_AT, received_at=QUOTED_AT + timedelta(seconds=2),
        market_session="OPEN", trading_status="NORMAL", provider_id="p",
        data_origin="GOLDEN_DATASET",
    )
    base.update(overrides)
    return QuoteContract(**base)


def _bar(trading_date, close, **overrides):
    base = dict(
        symbol=SYMBOL, timestamp=datetime.fromisoformat(f"{trading_date}T15:00:00"),
        trading_date=trading_date, open_price=close - 1, high_price=close + 1,
        low_price=close - 2, close_price=close, volume=1000.0, amount=close * 1000.0,
        adj_factor=1.0, unadjusted_close=close, trading_status="NORMAL",
        quality_status="VALID", data_origin="GOLDEN_DATASET",
    )
    base.update(overrides)
    return MarketDataContract(**base)


def _golden_provider(bars=None):
    bars = bars if bars is not None else [
        _bar("2024-02-01", 100.0), _bar("2024-02-02", 105.0),
    ]
    return GoldenQuoteProvider({SYMBOL: bars}, display_names={SYMBOL: "贵州茅台"})


# --- QuoteContract: computed change, never vendor-reported ------------------------------------

def test_change_and_change_pct_are_computed_from_the_two_prices_shown():
    quote = _quote(last_price=105.0, prev_close=100.0)
    assert quote.change == pytest.approx(5.0)
    assert quote.change_pct == pytest.approx(5.0)


def test_a_decline_is_reported_negative():
    quote = _quote(last_price=95.0, prev_close=100.0, high_price=101.0, low_price=94.0)
    assert quote.change == pytest.approx(-5.0)
    assert quote.change_pct == pytest.approx(-5.0)


def test_change_is_not_a_stored_field_that_could_disagree_with_the_prices():
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(QuoteContract)}
    assert "change" not in field_names and "change_pct" not in field_names


# --- QuoteContract: provenance drives the DEMO badge -------------------------------------------

def test_a_golden_quote_reports_itself_as_demo():
    assert _quote(data_origin="GOLDEN_DATASET").is_demo is True
    assert _quote(data_origin="SYNTHETIC_DATA").is_demo is True


def test_only_a_real_provider_quote_is_not_demo():
    assert _quote(data_origin="REAL_PROVIDER").is_demo is False


def test_unknown_data_origin_fails_closed():
    with pytest.raises(ValueError, match="unknown QuoteContract.data_origin"):
        _quote(data_origin="LIVE_MAYBE")


def test_unknown_trading_status_fails_closed():
    with pytest.raises(ValueError, match="unknown QuoteContract.trading_status"):
        _quote(trading_status="PROBABLY_OPEN")


# --- QuoteContract: fail-closed field validation -------------------------------------------------

@pytest.mark.parametrize("field_name", [
    "last_price", "prev_close", "open_price", "high_price", "low_price",
])
def test_non_positive_prices_fail_closed(field_name):
    with pytest.raises(ValueError, match="must be a positive price"):
        _quote(**{field_name: 0.0})


@pytest.mark.parametrize("field_name", ["volume", "amount"])
def test_negative_volume_or_amount_fails_closed(field_name):
    with pytest.raises(ValueError, match="must not be negative"):
        _quote(**{field_name: -1.0})


def test_zero_volume_is_accepted_for_a_suspended_name():
    assert _quote(volume=0.0, amount=0.0, trading_status="SUSPENDED").volume == 0.0


def test_receiving_a_quote_before_it_existed_fails_closed():
    with pytest.raises(ValueError, match="received_at precedes quoted_at"):
        _quote(received_at=QUOTED_AT - timedelta(seconds=1))


def test_empty_symbol_or_provider_fails_closed():
    with pytest.raises(ValueError, match="symbol must not be empty"):
        _quote(symbol="")
    with pytest.raises(ValueError, match="provider_id must not be empty"):
        _quote(provider_id="")


# --- age / freshness -------------------------------------------------------------------------------

def test_age_is_measured_from_the_vendor_timestamp_not_the_receipt_time():
    quote = _quote()
    assert quote.age_seconds(now=QUOTED_AT + timedelta(seconds=90)) == pytest.approx(90.0)


def test_age_never_goes_negative():
    assert _quote().age_seconds(now=QUOTED_AT - timedelta(seconds=30)) == 0.0


# --- GoldenQuoteProvider: honest about being demo ------------------------------------------------------

def test_golden_provider_implements_the_abc():
    assert isinstance(_golden_provider(), QuoteProvider)


def test_golden_quote_is_always_marked_golden_dataset():
    quote = _golden_provider().get_quote(SYMBOL)
    assert quote.data_origin == "GOLDEN_DATASET"
    assert quote.is_demo is True


def test_golden_provider_cannot_be_configured_to_claim_real_provider():
    """The provenance is hard-coded, not a constructor parameter — there is no way to pass
    REAL_PROVIDER into this class."""
    import inspect
    signature = inspect.signature(GoldenQuoteProvider.__init__)
    assert "data_origin" not in signature.parameters
    source = inspect.getsource(GoldenQuoteProvider)
    assert 'data_origin="GOLDEN_DATASET"' in source
    assert "REAL_PROVIDER" not in source.replace("can never claim REAL", "")


def test_golden_quote_is_stamped_with_the_historical_bar_time_not_now():
    """A demo quote stamped datetime.now() would look live. Its timestamp is the golden bar's
    own date, so its age is honestly enormous."""
    quote = _golden_provider().get_quote(SYMBOL)
    assert quote.quoted_at == datetime(2024, 2, 2, 15, 0, 0)
    assert quote.age_seconds(now=datetime(2026, 8, 3)) > 60 * 60 * 24 * 300


def test_golden_quote_derives_change_from_the_two_most_recent_bars():
    quote = _golden_provider().get_quote(SYMBOL)
    assert quote.last_price == 105.0
    assert quote.prev_close == 100.0
    assert quote.change_pct == pytest.approx(5.0)


def test_golden_provider_uses_the_latest_bar_regardless_of_input_order():
    unordered = [_bar("2024-02-02", 105.0), _bar("2024-02-01", 100.0)]
    quote = GoldenQuoteProvider({SYMBOL: unordered}).get_quote(SYMBOL)
    assert quote.last_price == 105.0


def test_unknown_symbol_refuses_rather_than_inventing_a_quote():
    with pytest.raises(ProviderError, match="refusing to invent a quote"):
        _golden_provider().get_quote("999999.XX")


def test_a_single_bar_fails_closed_because_change_would_be_misstated():
    provider = GoldenQuoteProvider({SYMBOL: [_bar("2024-02-01", 100.0)]})
    with pytest.raises(ProviderError, match="needs a previous close"):
        provider.get_quote(SYMBOL)


def test_golden_quote_passes_the_trust_gate():
    is_valid, errors = DataTrustGate.validate_quote(_golden_provider().get_quote(SYMBOL))
    assert is_valid, errors


# --- search --------------------------------------------------------------------------------------------

def test_search_matches_symbol_and_display_name():
    provider = _golden_provider()
    assert provider.search_symbols("600519")[0]["symbol"] == SYMBOL
    assert provider.search_symbols("茅台")[0]["symbol"] == SYMBOL
    assert provider.search_symbols("600519.sh")[0]["symbol"] == SYMBOL   # case-insensitive


def test_search_with_no_match_returns_empty_not_an_error():
    assert _golden_provider().search_symbols("NOT_A_SYMBOL") == []


def test_blank_search_returns_nothing_rather_than_everything():
    assert _golden_provider().search_symbols("   ") == []


# --- LiveQuoteProvider: refuses explicitly ------------------------------------------------------------------

def test_live_quote_provider_refuses_rather_than_returning_demo_data():
    provider = LiveQuoteProvider()
    assert isinstance(provider, QuoteProvider)
    with pytest.raises(ProviderError) as excinfo:
        provider.get_quote(SYMBOL)
    assert "QUOTE_PROVIDER_NOT_CONFIGURED" in str(excinfo.value)


def test_live_quote_provider_search_also_refuses():
    with pytest.raises(ProviderError, match="QUOTE_PROVIDER_NOT_CONFIGURED"):
        LiveQuoteProvider().search_symbols("600519")


def test_the_refusal_states_why_no_vendor_exists():
    assert "no real-time market-data vendor" in NO_QUOTE_VENDOR_REASON
    assert "never a fabricated live price" in NO_QUOTE_VENDOR_REASON


def test_no_quote_provider_makes_a_network_call():
    import inspect
    import src.data.providers.quote_provider as module
    source = inspect.getsource(module)
    for term in ("urlopen", "requests.", "httpx", "socket.", "http.client"):
        assert term not in source


# --- DataTrustGate.validate_quote ------------------------------------------------------------------------------

def test_a_coherent_quote_validates():
    is_valid, errors = DataTrustGate.validate_quote(_quote())
    assert is_valid and errors == []


def test_high_below_low_is_rejected():
    is_valid, errors = DataTrustGate.validate_quote(
        _quote(high_price=90.0, low_price=95.0, last_price=92.0, open_price=92.0)
    )
    assert not is_valid
    assert any("below low_price" in e for e in errors)


def test_last_price_outside_the_session_range_is_rejected():
    is_valid, errors = DataTrustGate.validate_quote(_quote(last_price=200.0))
    assert not is_valid
    assert any("last_price 200.0 lies outside" in e for e in errors)


def test_open_outside_the_session_range_is_rejected():
    is_valid, errors = DataTrustGate.validate_quote(_quote(open_price=1.0))
    assert not is_valid
    assert any("open_price" in e for e in errors)


@pytest.mark.parametrize("volume,amount,fragment", [
    (0.0, 100.0, "amount is positive but volume is zero"),
    (100.0, 0.0, "volume is positive but amount is zero"),
])
def test_incoherent_turnover_is_rejected(volume, amount, fragment):
    is_valid, errors = DataTrustGate.validate_quote(_quote(volume=volume, amount=amount))
    assert not is_valid
    assert any(fragment in e for e in errors)


def test_a_suspended_name_that_traded_is_rejected():
    is_valid, errors = DataTrustGate.validate_quote(_quote(trading_status="SUSPENDED"))
    assert not is_valid
    assert any("SUSPENDED but volume is positive" in e for e in errors)


def test_staleness_is_not_checked_unless_the_caller_asks():
    old = _quote(quoted_at=datetime(2020, 1, 1), received_at=datetime(2020, 1, 1))
    assert DataTrustGate.validate_quote(old)[0] is True


def test_staleness_is_reported_when_a_threshold_is_given():
    quote = _quote()
    is_valid, errors = DataTrustGate.validate_quote(
        quote, max_age_seconds=60, now=QUOTED_AT + timedelta(seconds=600)
    )
    assert not is_valid
    assert any("exceeding the caller's max_age_seconds" in e for e in errors)


def test_a_fresh_quote_passes_the_same_threshold():
    is_valid, _ = DataTrustGate.validate_quote(
        _quote(), max_age_seconds=60, now=QUOTED_AT + timedelta(seconds=10)
    )
    assert is_valid
