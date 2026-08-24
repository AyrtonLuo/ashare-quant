"""
test_history_provider_t35.py — real daily K-line history and the technical panel it feeds
(Terminal step T3.5).

Offline tests run against a local HTTP stub, so parsing, unit conversion and every failure path
are deterministic and network-free. One live test at the end actually calls the public endpoint
and is skipped — never failed — when the network is unavailable.

The property that matters most here: technical indicators in REAL mode are computed from REAL
bars, and a short or unavailable series produces 暂无数据 rather than anything borrowed.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.app import terminal_application as terminal
from src.data.providers.base import ProviderError
from src.data.providers.history_provider import (
    GoldenHistoryProvider,
    MarketHistoryProvider,
)
from src.data.providers.tencent_history_provider import (
    TENCENT_HISTORY_PROVIDER_ID,
    TencentHistoryProvider,
)
from src.data.validation.gate import DataTrustGate

SYMBOL = "600519.SH"
VENDOR_CODE = "sh600519"


def _rows(n=40, start_close=100.0):
    """[date, open, close, high, low, volume(手)] — the layout verified across 105 live bars.

    Dates advance with real calendar arithmetic; a naive f"2026-01-{i+1:02d}" runs past 2026-01-31
    and the provider rightly refuses those.
    """
    from datetime import date, timedelta

    first = date(2026, 1, 5)
    rows = []
    for i in range(n):
        close = start_close + i
        rows.append([
            (first + timedelta(days=i)).isoformat(), f"{close - 1:.3f}", f"{close:.3f}",
            f"{close + 2:.3f}", f"{close - 3:.3f}", f"{1000 + i}.000",
        ])
    return rows


class _StubState:
    status = 200
    body = ""
    last_path = None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _StubState.last_path = self.path
        payload = _StubState.body.encode("utf-8")
        self.send_response(_StubState.status)
        self.send_header("Content-Type", "application/json")
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
    yield f"http://127.0.0.1:{server.server_port}/get"
    server.shutdown()
    server.server_close()


def _body(rows=None, key="qfqday", code=0):
    return json.dumps({
        "code": code, "msg": "",
        "data": {VENDOR_CODE: {key: rows if rows is not None else _rows()}},
    })


def _provider(url):
    return TencentHistoryProvider(base_url=url)


# --- interface / dependencies -----------------------------------------------------------------

def test_implements_the_history_provider_interface(stub_url):
    provider = _provider(stub_url)
    assert isinstance(provider, MarketHistoryProvider)
    assert provider.provider_id == TENCENT_HISTORY_PROVIDER_ID
    assert provider.provider_version


def test_no_new_third_party_dependency():
    import inspect
    import src.data.providers.tencent_history_provider as module
    source = inspect.getsource(module)
    for dependency in ("import requests", "import httpx", "import pandas", "import akshare",
                       "import tushare"):
        assert dependency not in source


def test_the_price_basis_is_declared_by_the_provider_not_guessed(stub_url):
    """A caller that assumes the basis attaches a false adjustment claim to every indicator."""
    assert _provider(stub_url).input_price_basis == "VENDOR_FORWARD_ADJUSTED"
    assert GoldenHistoryProvider({}).input_price_basis == "RAW"


# --- parsing ------------------------------------------------------------------------------------

def test_a_live_shaped_payload_parses_into_real_provider_bars(stub_url):
    _StubState.body = _body()
    bars = _provider(stub_url).get_daily_bars(SYMBOL, limit=40)

    assert len(bars) == 40
    assert all(b.data_origin == "REAL_PROVIDER" for b in bars)
    assert all(b.symbol == SYMBOL for b in bars)
    first = bars[0]
    assert first.trading_date == "2026-01-05"
    assert first.open_price == pytest.approx(99.0)
    assert first.close_price == pytest.approx(100.0)
    assert first.high_price == pytest.approx(102.0)
    assert first.low_price == pytest.approx(97.0)


def test_volume_is_converted_from_lots_to_shares(stub_url):
    """The vendor reports 手; the contract stores shares. Getting this wrong is a 100x error."""
    _StubState.body = _body()
    bars = _provider(stub_url).get_daily_bars(SYMBOL, limit=40)
    assert bars[0].volume == pytest.approx(1000.0 * 100)


def test_bars_are_returned_ascending_by_date(stub_url):
    _StubState.body = _body(list(reversed(_rows())))
    bars = _provider(stub_url).get_daily_bars(SYMBOL, limit=40)
    assert [b.trading_date for b in bars] == sorted(b.trading_date for b in bars)


def test_every_bar_passes_the_trust_gate(stub_url):
    _StubState.body = _body()
    for bar in _provider(stub_url).get_daily_bars(SYMBOL, limit=40):
        is_valid, errors = DataTrustGate.validate_market_data(bar)
        assert is_valid, errors


def test_the_adjusted_series_is_requested(stub_url):
    _StubState.body = _body()
    _provider(stub_url).get_daily_bars(SYMBOL, limit=40)
    assert "qfq" in _StubState.last_path
    assert VENDOR_CODE in _StubState.last_path


# --- fail-closed paths -----------------------------------------------------------------------------

def test_an_unadjusted_only_payload_is_refused_not_substituted(stub_url):
    """Falling back to the raw series would silently contradict the declared price basis."""
    _StubState.body = _body(key="day")
    with pytest.raises(ProviderError, match="refusing to substitute the unadjusted one"):
        _provider(stub_url).get_daily_bars(SYMBOL)


def test_a_transposed_field_order_is_detected(stub_url):
    """The layout is positional and undocumented — open and close are adjacent. If the vendor
    reorders, high/low invariants break and the provider refuses rather than showing wrong
    prices."""
    bad = [["2026-01-01", "150.000", "100.000", "90.000", "80.000", "1000.000"]]
    _StubState.body = _body(bad)
    with pytest.raises(ProviderError, match="violates high/low bounds"):
        _provider(stub_url).get_daily_bars(SYMBOL)


def test_an_unknown_code_is_refused(stub_url):
    _StubState.body = json.dumps({"code": 0, "data": {}})
    with pytest.raises(ProviderError, match="has no data"):
        _provider(stub_url).get_daily_bars(SYMBOL)


def test_an_empty_series_is_refused(stub_url):
    _StubState.body = _body([])
    with pytest.raises(ProviderError, match="no bars"):
        _provider(stub_url).get_daily_bars(SYMBOL)


def test_a_short_row_is_refused(stub_url):
    _StubState.body = _body([["2026-01-01", "1.0", "2.0"]])
    with pytest.raises(ProviderError, match="fewer than"):
        _provider(stub_url).get_daily_bars(SYMBOL)


def test_a_non_numeric_field_is_refused(stub_url):
    _StubState.body = _body([["2026-01-01", "n/a", "100.0", "102.0", "98.0", "1000.0"]])
    with pytest.raises(ProviderError, match="non-numeric"):
        _provider(stub_url).get_daily_bars(SYMBOL)


def test_a_bad_date_is_refused(stub_url):
    _StubState.body = _body([["not-a-date", "99.0", "100.0", "102.0", "98.0", "1000.0"]])
    with pytest.raises(ProviderError, match="bad date"):
        _provider(stub_url).get_daily_bars(SYMBOL)


def test_a_non_positive_close_is_refused(stub_url):
    _StubState.body = _body([["2026-01-01", "0.0", "0.0", "0.0", "0.0", "1000.0"]])
    with pytest.raises(ProviderError, match="non-positive close"):
        _provider(stub_url).get_daily_bars(SYMBOL)


def test_malformed_json_is_refused(stub_url):
    _StubState.body = "not json"
    with pytest.raises(ProviderError, match="not valid JSON"):
        _provider(stub_url).get_daily_bars(SYMBOL)


def test_an_http_error_is_reported(stub_url):
    _StubState.status, _StubState.body = 503, "{}"
    with pytest.raises(ProviderError, match="HTTP 503"):
        _provider(stub_url).get_daily_bars(SYMBOL)


def test_an_unreachable_endpoint_is_reported():
    with pytest.raises(ProviderError, match="could not reach"):
        TencentHistoryProvider(base_url="http://127.0.0.1:1/get",
                               timeout_seconds=2.0).get_daily_bars(SYMBOL)


@pytest.mark.parametrize("symbol", ["600519", "600519.XX", "ABCDEF.SH", ""])
def test_an_unmappable_symbol_is_refused_rather_than_guessed(stub_url, symbol):
    with pytest.raises(ProviderError):
        _provider(stub_url).get_daily_bars(symbol)


def test_an_invalid_limit_is_refused(stub_url):
    with pytest.raises(ProviderError, match="invalid bar limit"):
        _provider(stub_url).get_daily_bars(SYMBOL, limit=0)


def test_a_repeat_request_is_served_from_cache(stub_url):
    _StubState.body = _body()
    provider = _provider(stub_url)
    first = provider.get_daily_bars(SYMBOL, limit=40)
    _StubState.last_path = None
    assert provider.get_daily_bars(SYMBOL, limit=40) is first
    assert _StubState.last_path is None


# --- the technical panel it feeds -------------------------------------------------------------------

def test_demo_mode_computes_indicators_from_demo_bars():
    history = terminal.get_price_history(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    assert history.is_demo is True
    assert history.bar_count > 0
    assert "演示" in history.data_source

    readings = terminal.get_technical_views(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    assert any(r.available for r in readings)


def test_each_indicator_decides_availability_on_its_own_warm_up():
    """The demo set has 25 bars: enough for MA20/RSI14 but not for MACD's 34. A single blanket
    threshold would have hidden five perfectly computable readings."""
    readings = {r.name: r for r in terminal.get_technical_views(SYMBOL,
                                                               terminal.QUOTE_SOURCE_DEMO)}
    assert readings["趋势 (20日均线)"].available is True
    assert readings["MACD (动能)"].available is False
    assert "不会用其他数据补齐" in readings["MACD (动能)"].explanation


def test_an_unavailable_series_reports_every_row_as_unavailable(monkeypatch):
    """No partial panel, and nothing borrowed from the other mode."""
    def _failing(source=None):
        raise terminal.TerminalError("模拟：历史行情源不可用")

    monkeypatch.setattr(terminal, "_history_provider", _failing)
    readings = terminal.get_technical_views(SYMBOL, terminal.QUOTE_SOURCE_REAL)
    assert len(readings) == len(terminal._TECHNICAL_PANEL_NAMES)
    assert all(not r.available for r in readings)
    assert all("历史行情源不可用" in r.explanation for r in readings)


def test_a_failed_history_fetch_yields_an_empty_chart_with_a_reason(monkeypatch):
    def _failing(source=None):
        raise terminal.TerminalError("模拟：历史行情源不可用")

    monkeypatch.setattr(terminal, "_history_provider", _failing)
    history = terminal.get_price_history(SYMBOL, terminal.QUOTE_SOURCE_REAL)
    assert history.bar_count == 0
    assert history.dates == ()
    assert history.unavailable_reason


def test_one_incoherent_bar_refuses_the_whole_series_rather_than_repairing_it(stub_url):
    """A corrupt bar is never silently corrected or dropped-and-forgotten: the provider refuses,
    so a partially-wrong series can never reach an indicator."""
    rows = _rows(40)
    rows[5][2] = "-5.000"          # a negative close inside an otherwise clean series
    rows[5][3] = "-1.000"
    rows[5][4] = "-9.000"
    _StubState.body = _body(rows)

    with pytest.raises(ProviderError):
        _provider(stub_url).get_daily_bars(SYMBOL, limit=40)


# --- the live endpoint ----------------------------------------------------------------------------------

@pytest.mark.real_provider
def test_live_history_and_real_technical_panel():
    """API → Adapter → Contract → Validation → Technical Indicators, against the real endpoint."""
    provider = TencentHistoryProvider()
    try:
        bars = provider.get_daily_bars(SYMBOL, limit=120)
    except ProviderError as e:
        pytest.skip(f"LIVE_HISTORY_UNAVAILABLE: {e}")

    assert len(bars) >= 34, "expected enough history for a full technical panel"
    assert all(b.data_origin == "REAL_PROVIDER" for b in bars)
    for bar in bars:
        is_valid, errors = DataTrustGate.validate_market_data(bar)
        assert is_valid, errors
    assert [b.trading_date for b in bars] == sorted(b.trading_date for b in bars)

    readings = terminal.get_technical_views(SYMBOL, terminal.QUOTE_SOURCE_REAL)
    assert all(r.available for r in readings), [r.name for r in readings if not r.available]
    assert {r.name for r in readings} == set(terminal._TECHNICAL_PANEL_NAMES)

    history = terminal.get_price_history(SYMBOL, terminal.QUOTE_SOURCE_REAL)
    assert history.is_demo is False
    assert history.bar_count >= 34
    assert "GOLDEN" not in history.data_source
