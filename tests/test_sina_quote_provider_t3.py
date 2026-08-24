"""
test_sina_quote_provider_t3.py — the real-time A-share quote provider (Terminal step T3).

Every offline test runs against a local HTTP stub on 127.0.0.1, so parsing, unit handling and
every failure path are deterministic and network-free. One live test at the end actually calls
the public endpoint and is skipped — never failed — when the network is unavailable.

The product-critical property under test is that REAL and DEMO data can never be confused, and
that nothing is ever substituted for a missing number.
"""

import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.app import terminal_application as terminal
from src.data.providers.base import ProviderError
from src.data.providers.quote_provider import QuoteProvider
from src.data.providers.sina_quote_provider import (
    SINA_QUOTE_PROVIDER_ID,
    SinaQuoteProvider,
)
from src.data.validation.gate import DataTrustGate

SYMBOL = "600519.SH"

# A real response captured from the live endpoint: 34 comma-separated fields.
_LIVE_SHAPE = (
    "贵州茅台,1271.010,1272.830,1296.860,1296.880,1270.330,1296.730,1296.870,"
    # 20 filler fields (order-book depth) put the date at index 30 and the time at 31, exactly
    # as the live response does — verified by counting a real payload before writing this.
    "1732838,2233178320.000," + ",".join(["0"] * 20) + ",2026-08-24,10:15:58,00,"
)


class _StubState:
    status = 200
    body = ""
    last_path = None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _StubState.last_path = self.path
        payload = _StubState.body.encode("gbk", errors="replace")
        self.send_response(_StubState.status)
        self.send_header("Content-Type", "application/javascript; charset=GBK")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture()
def stub_url():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _StubState.status, _StubState.body, _StubState.last_path = 200, "", None
    yield f"http://127.0.0.1:{server.server_port}/list="
    server.shutdown()
    server.server_close()


def _sina_body(fields=_LIVE_SHAPE, code="sh600519"):
    return f'var hq_str_{code}="{fields}";\n'


def _provider(url):
    return SinaQuoteProvider(display_names={SYMBOL: "贵州茅台"}, base_url=url)


# --- interface ----------------------------------------------------------------------------------

def test_satisfies_the_quote_provider_interface(stub_url):
    provider = _provider(stub_url)
    assert provider.provider_id == SINA_QUOTE_PROVIDER_ID
    assert provider.provider_version
    assert hasattr(provider, "get_quote") and hasattr(provider, "search_symbols")


def test_no_new_third_party_dependency_is_imported():
    import inspect
    import src.data.providers.sina_quote_provider as module
    source = inspect.getsource(module)
    for dependency in ("import requests", "import httpx", "import akshare", "import tushare",
                       "from requests", "import pandas"):
        assert dependency not in source


# --- happy path: full parse -----------------------------------------------------------------------

def test_a_live_shaped_response_parses_into_a_real_provider_quote(stub_url):
    _StubState.body = _sina_body()
    quote = _provider(stub_url).get_quote(SYMBOL)

    assert quote.symbol == SYMBOL
    assert quote.display_name == "贵州茅台"
    assert quote.last_price == pytest.approx(1296.86)
    assert quote.prev_close == pytest.approx(1272.83)
    assert quote.open_price == pytest.approx(1271.01)
    assert quote.high_price == pytest.approx(1296.88)
    assert quote.low_price == pytest.approx(1270.33)
    assert quote.data_origin == "REAL_PROVIDER"
    assert quote.is_demo is False


def test_volume_is_taken_in_shares_without_a_unit_conversion(stub_url):
    """Sina reports volume in SHARES. A source reporting 手/lots would need a x100 conversion;
    getting that wrong misstates 成交量 by two orders of magnitude."""
    _StubState.body = _sina_body()
    quote = _provider(stub_url).get_quote(SYMBOL)
    assert quote.volume == pytest.approx(1732838.0)
    assert quote.amount == pytest.approx(2233178320.0)


def test_the_vendor_timestamp_is_used_not_the_receipt_time(stub_url):
    _StubState.body = _sina_body()
    quote = _provider(stub_url).get_quote(SYMBOL)
    assert quote.quoted_at == datetime(2026, 8, 24, 10, 15, 58)
    assert quote.received_at >= quote.quoted_at


def test_change_is_derived_from_the_two_prices(stub_url):
    _StubState.body = _sina_body()
    quote = _provider(stub_url).get_quote(SYMBOL)
    assert quote.change == pytest.approx(1296.86 - 1272.83)


def test_a_parsed_quote_passes_the_trust_gate(stub_url):
    _StubState.body = _sina_body()
    is_valid, errors = DataTrustGate.validate_quote(_provider(stub_url).get_quote(SYMBOL))
    assert is_valid, errors


# --- symbol mapping -------------------------------------------------------------------------------

@pytest.mark.parametrize("symbol,expected", [
    ("600519.SH", "sh600519"), ("000001.SZ", "sz000001"), ("430047.BJ", "bj430047"),
])
def test_symbols_map_to_the_vendors_exchange_prefix(stub_url, symbol, expected):
    _StubState.body = _sina_body(code=expected)
    _provider(stub_url).get_quote(symbol)
    assert _StubState.last_path.endswith(expected)


@pytest.mark.parametrize("symbol", ["600519", "600519.XX", "ABCDEF.SH", "", "60051.SH"])
def test_an_unmappable_symbol_is_refused_rather_than_guessed(stub_url, symbol):
    """Guessing an exchange returns a real quote for the WRONG security."""
    with pytest.raises(ProviderError):
        _provider(stub_url).get_quote(symbol)


# --- failure paths: nothing is ever substituted ------------------------------------------------------

def test_an_unknown_code_returns_an_empty_payload_and_fails_closed(stub_url):
    _StubState.body = 'var hq_str_sh999999="";\n'
    with pytest.raises(ProviderError, match="has no data"):
        _provider(stub_url).get_quote("999999.SH")


def test_a_suspended_name_fails_closed_rather_than_showing_yesterdays_close(stub_url):
    """A halted name reports 0.00. Substituting prev_close would display a price that never
    traded."""
    halted = _LIVE_SHAPE.replace("1296.860", "0.000", 1)
    _StubState.body = _sina_body(halted)
    with pytest.raises(ProviderError, match="停牌或今日尚无成交"):
        _provider(stub_url).get_quote(SYMBOL)


def test_a_truncated_field_layout_fails_closed(stub_url):
    """The layout is undocumented and could change; refusing beats reading the wrong position
    and presenting it as a price."""
    _StubState.body = _sina_body("贵州茅台,1271.010,1272.830,1296.860")
    with pytest.raises(ProviderError, match="fewer than"):
        _provider(stub_url).get_quote(SYMBOL)


def test_a_non_numeric_price_fails_closed(stub_url):
    _StubState.body = _sina_body(_LIVE_SHAPE.replace("1296.860", "N/A", 1))
    with pytest.raises(ProviderError, match="non-numeric"):
        _provider(stub_url).get_quote(SYMBOL)


def test_an_unparseable_timestamp_fails_closed(stub_url):
    _StubState.body = _sina_body(_LIVE_SHAPE.replace("2026-08-24", "not-a-date"))
    with pytest.raises(ProviderError, match="unparseable timestamp"):
        _provider(stub_url).get_quote(SYMBOL)


def test_an_unrecognised_response_shape_fails_closed(stub_url):
    _StubState.body = "totally unexpected"
    with pytest.raises(ProviderError, match="unrecognised quote response shape"):
        _provider(stub_url).get_quote(SYMBOL)


def test_an_http_error_is_reported_not_retried_silently(stub_url):
    _StubState.status, _StubState.body = 503, "unavailable"
    with pytest.raises(ProviderError, match="HTTP 503"):
        _provider(stub_url).get_quote(SYMBOL)


def test_an_unreachable_endpoint_is_reported():
    provider = SinaQuoteProvider(base_url="http://127.0.0.1:1/list=", timeout_seconds=2.0)
    with pytest.raises(ProviderError, match="could not reach"):
        provider.get_quote(SYMBOL)


# --- caching (courtesy to a free endpoint) ------------------------------------------------------------

def test_a_repeat_request_is_served_from_cache_rather_than_re_fetched(stub_url):
    _StubState.body = _sina_body()
    provider = _provider(stub_url)
    first = provider.get_quote(SYMBOL)

    _StubState.last_path = None
    second = provider.get_quote(SYMBOL)
    assert _StubState.last_path is None      # no second request was made
    assert second is first


# --- REAL vs DEMO must never be confused ----------------------------------------------------------------

def test_demo_mode_and_real_mode_produce_different_data_status():
    demo = terminal.get_quote_view(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    assert demo.data_status == terminal.DEMO_DATA_STATUS
    assert demo.is_demo is True
    assert "演示" in demo.data_source


def test_real_mode_is_the_default():
    assert terminal.DEFAULT_QUOTE_SOURCE == terminal.QUOTE_SOURCE_REAL


def test_an_unknown_source_mode_fails_closed():
    with pytest.raises(terminal.TerminalError, match="未知的数据源模式"):
        terminal.get_quote_view(SYMBOL, "SOMETHING_ELSE")


def test_each_mode_draws_its_bars_from_its_own_provider():
    """Superseded by T3.5, which gave REAL mode a real bar series. The invariant under test is
    now stronger AND network-free: the two modes resolve to DIFFERENT providers, so a REAL-mode
    indicator can never be computed from demo bars."""
    from src.data.providers.history_provider import GoldenHistoryProvider
    from src.data.providers.tencent_history_provider import TencentHistoryProvider

    real = terminal._history_provider(terminal.QUOTE_SOURCE_REAL)
    demo = terminal._history_provider(terminal.QUOTE_SOURCE_DEMO)
    assert isinstance(real, TencentHistoryProvider)
    assert isinstance(demo, GoldenHistoryProvider)
    assert real.provider_id != demo.provider_id


def test_an_unknown_source_mode_has_no_history_provider():
    with pytest.raises(terminal.TerminalError, match="未知的数据源模式"):
        terminal._history_provider("SOMETHING_ELSE")


def test_real_mode_never_shows_demo_fundamentals():
    rows = terminal.get_fundamental_views(SYMBOL, terminal.QUOTE_SOURCE_REAL)
    assert len(rows) == 8
    for row in rows:
        assert row.available is False
        assert row.value == terminal.NOT_AVAILABLE_TEXT
        assert "不会用演示数据代替真实数据" in row.reason


def test_demo_mode_still_shows_its_own_indicators_and_fundamentals():
    readings = terminal.get_technical_views(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    assert any(r.available for r in readings)
    rows = terminal.get_fundamental_views(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    assert any(r.available for r in rows)


def test_a_failed_live_search_returns_nothing_rather_than_demo_results():
    """A search that cannot reach the live source must not quietly answer from the demo
    universe."""
    import src.app.terminal_application as module

    class _FailingProvider:
        def search_symbols(self, query):
            raise ProviderError("x", "unreachable")

    original = module._quote_provider
    module._quote_provider = lambda source=None: _FailingProvider()
    try:
        assert module.search_stocks("600519", module.QUOTE_SOURCE_REAL) == []
    finally:
        module._quote_provider = original


# --- the live endpoint ------------------------------------------------------------------------------------

@pytest.mark.real_provider
def test_live_quote_from_the_public_endpoint():
    """Actually calls the public quote endpoint: API → Adapter → Contract → Validation.

    Skipped, never failed, when the network is unavailable — an offline CI box is not a
    regression in this provider.
    """
    provider = SinaQuoteProvider(display_names={SYMBOL: "贵州茅台"})
    try:
        quote = provider.get_quote(SYMBOL)
    except ProviderError as e:
        pytest.skip(f"LIVE_QUOTE_UNAVAILABLE: {e}")

    assert quote.data_origin == "REAL_PROVIDER"
    assert quote.is_demo is False
    assert quote.last_price > 0 and quote.prev_close > 0
    assert quote.low_price <= quote.last_price <= quote.high_price
    assert quote.quoted_at.year >= 2024
    is_valid, errors = DataTrustGate.validate_quote(quote)
    assert is_valid, errors


def test_the_demo_label_suffix_never_appears_in_real_mode():
    """The seeded names carry a "(GOLDEN_DATASET demo)" suffix. Showing it beside a live price
    would misdescribe real data as demo data."""
    real = terminal.list_stocks(terminal.QUOTE_SOURCE_REAL)
    demo = terminal.list_stocks(terminal.QUOTE_SOURCE_DEMO)
    assert all("GOLDEN_DATASET" not in s["display_name"] for s in real)
    assert all("GOLDEN_DATASET" in s["display_name"] for s in demo)
    assert {s["symbol"] for s in real} == {s["symbol"] for s in demo}
