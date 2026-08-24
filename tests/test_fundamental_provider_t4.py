"""
test_fundamental_provider_t4.py — real fundamental / valuation data (Terminal step T4).

Offline tests run against a local HTTP stub, so parsing, the field-order guard and every failure
path are deterministic and network-free. One live test at the end calls the public endpoint and
is skipped — never failed — when the network is unavailable.

The properties that matter here: nothing shown is estimated, PB is the vendor's own number rather
than a derivation, REAL and DEMO cannot cross-contaminate, and the fundamental panel declares its
OWN source and date rather than inheriting the quote's.
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.app import terminal_application as terminal
from src.data.providers.base import ProviderError
from src.data.providers.fundamental_provider import (
    REPORT_PERIOD_NOT_DISCLOSED,
    FundamentalProvider,
    GoldenFundamentalProvider,
)
from src.data.providers.tencent_fundamental_provider import (
    TENCENT_FUNDAMENTAL_PROVIDER_ID,
    TencentFundamentalProvider,
)
from src.data.validation.gate import DataTrustGate

SYMBOL = "600519.SH"
VENDOR_CODE = "sh600519"

# A response shaped like the live one. Field positions were verified across three symbols —
# including a dual-listed name — before the parser was written; see the provider's docstring.
_PRICE = "1307.30"
_PE = "20.07"
_PB = "6.50"
_TOTAL_SHARES = "1250081601"
_TOTAL_MARKET_CAP_YI = "16342.32"        # == 1307.30 * 1250081601 / 1e8
_FLOAT_MARKET_CAP_YI = "16342.32"


def _fields(**overrides):
    f = ["1"] * 88
    f[1], f[2], f[3] = "贵州茅台", "600519", _PRICE
    f[30] = "20260824112025"
    f[39] = _PE
    f[44] = _FLOAT_MARKET_CAP_YI
    f[45] = _TOTAL_MARKET_CAP_YI
    f[46] = _PB
    f[73] = _TOTAL_SHARES
    for index, value in overrides.items():
        f[int(index)] = value
    return f


def _body(fields=None, code=VENDOR_CODE):
    return f'v_{code}="' + "~".join(fields if fields is not None else _fields()) + '";\n'


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
    yield f"http://127.0.0.1:{server.server_port}/q="
    server.shutdown()
    server.server_close()


def _provider(url):
    return TencentFundamentalProvider(base_url=url)


# --- interface / dependencies -------------------------------------------------------------------

def test_implements_the_fundamental_provider_interface(stub_url):
    provider = _provider(stub_url)
    assert isinstance(provider, FundamentalProvider)
    assert provider.provider_id == TENCENT_FUNDAMENTAL_PROVIDER_ID
    assert provider.provider_version


def test_the_source_declares_its_own_label_separate_from_quote_and_history(stub_url):
    """Directive: quotes, K-line history and fundamentals must not be collapsed into one source
    claim."""
    label = _provider(stub_url).source_label
    assert TENCENT_FUNDAMENTAL_PROVIDER_ID in label
    assert "估值" in label
    assert label != GoldenFundamentalProvider({}).source_label


def test_no_new_third_party_dependency():
    import inspect
    import src.data.providers.tencent_fundamental_provider as module
    source = inspect.getsource(module)
    for dependency in ("import requests", "import httpx", "import pandas", "import akshare",
                       "import tushare"):
        assert dependency not in source


# --- happy path ------------------------------------------------------------------------------------

def test_a_live_shaped_response_parses_into_a_real_provider_contract(stub_url):
    _StubState.body = _body()
    contract = _provider(stub_url).get_fundamentals(SYMBOL)

    assert contract.symbol == SYMBOL
    assert contract.data_origin == "REAL_PROVIDER"
    assert contract.pe_ttm == pytest.approx(20.07)
    assert contract.pb == pytest.approx(6.50)
    assert contract.shares_outstanding == pytest.approx(1250081601)
    assert contract.market_cap == pytest.approx(float(_TOTAL_MARKET_CAP_YI) * 1e8)
    assert contract.trade_date == "2026-08-24"
    assert contract.provider == TENCENT_FUNDAMENTAL_PROVIDER_ID


def test_a_parsed_contract_passes_the_trust_gate(stub_url):
    _StubState.body = _body()
    is_valid, errors = DataTrustGate.validate_fundamental_data(
        _provider(stub_url).get_fundamentals(SYMBOL))
    assert is_valid, errors


def test_total_share_capital_is_used_not_the_tradable_float(stub_url):
    """Field 73 was pinned as TOTAL share capital because it satisfies the market-cap identity
    for a dual-listed name where the tradable-float fields do not."""
    _StubState.body = _body()
    contract = _provider(stub_url).get_fundamentals(SYMBOL)
    implied = contract.shares_outstanding * float(_PRICE) / 1e8
    assert implied == pytest.approx(float(_TOTAL_MARKET_CAP_YI), rel=1e-4)


# --- nothing is estimated ---------------------------------------------------------------------------

def test_pb_is_the_vendors_own_number_never_derived(stub_url):
    """A derived price / 每股净资产 was WRONG for a dual-listed name (2.800 vs the vendor's 3.19),
    which is exactly why this provider reports the vendor's PB and computes none."""
    import inspect
    import src.data.providers.tencent_fundamental_provider as module
    source = inspect.getsource(module)
    assert "book_value_per_share=None" in source
    _StubState.body = _body(_fields(**{"46": "3.19"}))
    assert _provider(stub_url).get_fundamentals(SYMBOL).pb == pytest.approx(3.19)


@pytest.mark.parametrize("attribute", [
    "revenue", "net_income", "eps_ttm", "eps_annual", "roe", "book_value_per_share",
    "operating_cash_flow", "pe_lyr", "dividend_yield_ttm",
])
def test_unreported_metrics_are_none_never_estimated(stub_url, attribute):
    """No free source was found that reports these verifiably, so they stay None and surface as
    暂无数据 — never computed from something else and presented as vendor data."""
    _StubState.body = _body()
    assert getattr(_provider(stub_url).get_fundamentals(SYMBOL), attribute) is None


def test_a_blank_vendor_metric_becomes_none_not_zero(stub_url):
    """The vendor blanks PE for a loss-making company. 0.0 would read as a real measurement."""
    _StubState.body = _body(_fields(**{"39": "", "46": "0.00"}))
    contract = _provider(stub_url).get_fundamentals(SYMBOL)
    assert contract.pe_ttm is None and contract.pe_ttm_status == "UNAVAILABLE"
    assert contract.pb is None and contract.pb_status == "UNAVAILABLE"


def test_an_undisclosed_report_period_is_stated_not_invented(stub_url):
    _StubState.body = _body()
    contract = _provider(stub_url).get_fundamentals(SYMBOL)
    assert contract.report_date == REPORT_PERIOD_NOT_DISCLOSED
    assert contract.announcement_date == REPORT_PERIOD_NOT_DISCLOSED


# --- the field-order guard ----------------------------------------------------------------------------

def test_a_broken_market_cap_identity_is_refused(stub_url):
    """The identity is what pinned the share-capital field. Re-checking it on every fetch turns a
    silent vendor reordering into a refusal instead of a wrong market cap."""
    _StubState.body = _body(_fields(**{"73": "999"}))
    with pytest.raises(ProviderError, match="fails its own market-cap identity"):
        _provider(stub_url).get_fundamentals(SYMBOL)


def test_a_small_identity_drift_is_tolerated(stub_url):
    """Price and market cap can be sampled a moment apart, so the check has a tolerance rather
    than demanding exact equality."""
    drifted = float(_TOTAL_MARKET_CAP_YI) * 1.005
    _StubState.body = _body(_fields(**{"45": f"{drifted:.2f}"}))
    assert _provider(stub_url).get_fundamentals(SYMBOL).pe_ttm == pytest.approx(20.07)


# --- fail-closed paths ----------------------------------------------------------------------------------

def test_an_unknown_code_is_refused(stub_url):
    _StubState.body = f'v_{VENDOR_CODE}="";\n'
    with pytest.raises(ProviderError, match="has no data"):
        _provider(stub_url).get_fundamentals(SYMBOL)


def test_a_truncated_field_list_is_refused(stub_url):
    _StubState.body = _body(["1"] * 10)
    with pytest.raises(ProviderError, match="fewer than"):
        _provider(stub_url).get_fundamentals(SYMBOL)


def test_a_non_numeric_required_field_is_refused(stub_url):
    _StubState.body = _body(_fields(**{"3": "n/a"}))
    with pytest.raises(ProviderError, match="non-numeric"):
        _provider(stub_url).get_fundamentals(SYMBOL)


@pytest.mark.parametrize("index", ["3", "45", "73"])
def test_a_non_positive_core_value_is_refused(stub_url, index):
    _StubState.body = _body(_fields(**{index: "0"}))
    with pytest.raises(ProviderError):
        _provider(stub_url).get_fundamentals(SYMBOL)


def test_an_unparseable_timestamp_is_refused(stub_url):
    _StubState.body = _body(_fields(**{"30": "not-a-stamp"}))
    with pytest.raises(ProviderError, match="unparseable timestamp"):
        _provider(stub_url).get_fundamentals(SYMBOL)


def test_an_unrecognised_response_shape_is_refused(stub_url):
    _StubState.body = "totally unexpected"
    with pytest.raises(ProviderError, match="unrecognised valuation response shape"):
        _provider(stub_url).get_fundamentals(SYMBOL)


def test_an_http_error_is_reported(stub_url):
    _StubState.status, _StubState.body = 503, "unavailable"
    with pytest.raises(ProviderError, match="HTTP 503"):
        _provider(stub_url).get_fundamentals(SYMBOL)


def test_an_unreachable_endpoint_is_reported():
    with pytest.raises(ProviderError, match="could not reach"):
        TencentFundamentalProvider(base_url="http://127.0.0.1:1/q=",
                                   timeout_seconds=2.0).get_fundamentals(SYMBOL)


@pytest.mark.parametrize("symbol", ["600519", "600519.XX", "ABCDEF.SH", ""])
def test_an_unmappable_symbol_is_refused_rather_than_guessed(stub_url, symbol):
    with pytest.raises(ProviderError):
        _provider(stub_url).get_fundamentals(symbol)


def test_a_repeat_request_is_served_from_cache(stub_url):
    _StubState.body = _body()
    provider = _provider(stub_url)
    first = provider.get_fundamentals(SYMBOL)
    _StubState.last_path = None
    assert provider.get_fundamentals(SYMBOL) is first
    assert _StubState.last_path is None


# --- the Terminal panel ------------------------------------------------------------------------------------

def test_the_panel_always_lists_every_row_the_directive_names():
    panel = terminal.get_fundamentals_panel(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    labels = [row.label for row in panel.rows]
    for required in ("总市值", "市盈率 (PE)", "市净率 (PB)", "净资产收益率 (ROE)", "营收",
                     "净利润", "毛利率", "净利率", "每股收益 (EPS)"):
        assert required in labels


def test_every_missing_row_carries_a_reason():
    panel = terminal.get_fundamentals_panel(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    for row in panel.rows:
        if not row.available:
            assert row.value == terminal.NOT_AVAILABLE_TEXT
            assert row.reason, f"{row.label} has no reason"


def test_a_metric_no_source_reports_is_distinguished_from_one_the_source_omits():
    """"the source does not report it" and "it is not modelled anywhere" are different facts."""
    rows = {r.label: r for r in
            terminal.get_fundamentals_panel(SYMBOL, terminal.QUOTE_SOURCE_DEMO).rows}
    assert "尚未纳入当前数据契约" in rows["毛利率"].reason
    assert "不做估算" in rows["毛利率"].reason
    assert "数据源未提供" in rows["营收"].reason


def test_the_panel_carries_its_own_source_and_date():
    panel = terminal.get_fundamentals_panel(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    assert panel.data_source and panel.data_date
    assert panel.is_demo is True
    assert "演示" in panel.data_source


def test_a_failed_fetch_reports_every_row_unavailable_with_the_reason(monkeypatch):
    """No partial panel, and nothing borrowed from the other mode."""
    def _failing(source=None):
        raise terminal.TerminalError("模拟：基本面数据源不可用")

    monkeypatch.setattr(terminal, "_fundamental_provider", _failing)
    panel = terminal.get_fundamentals_panel(SYMBOL, terminal.QUOTE_SOURCE_REAL)
    assert panel.unavailable_reason
    assert len(panel.rows) == 9
    assert all(not row.available for row in panel.rows)
    assert all("基本面数据源不可用" in row.reason for row in panel.rows)


def test_an_unknown_symbol_yields_an_unavailable_panel_not_an_exception():
    panel = terminal.get_fundamentals_panel("999999.XX", terminal.QUOTE_SOURCE_DEMO)
    assert panel.unavailable_reason
    assert all(not row.available for row in panel.rows)


def test_demo_mode_shows_the_demo_dataset_value():
    rows = {r.label: r for r in
            terminal.get_fundamentals_panel(SYMBOL, terminal.QUOTE_SOURCE_DEMO).rows}
    assert rows["市盈率 (PE)"].available is True


# --- the live endpoint ----------------------------------------------------------------------------------------

@pytest.mark.real_provider
def test_live_fundamentals_from_the_public_endpoint():
    """API → Adapter → Contract → Validation, against the real endpoint."""
    provider = TencentFundamentalProvider()
    try:
        contract = provider.get_fundamentals(SYMBOL)
    except ProviderError as e:
        pytest.skip(f"LIVE_FUNDAMENTALS_UNAVAILABLE: {e}")

    assert contract.data_origin == "REAL_PROVIDER"
    assert contract.market_cap > 0 and contract.shares_outstanding > 0
    assert contract.pe_ttm is None or contract.pe_ttm > 0
    assert contract.pb is None or contract.pb > 0
    is_valid, errors = DataTrustGate.validate_fundamental_data(contract)
    assert is_valid, errors

    # An ADDITIONAL live call via the Application Layer; a transient outage skips rather than
    # failing, exactly as the fetch above does.
    panel = terminal.get_fundamentals_panel(SYMBOL, terminal.QUOTE_SOURCE_REAL)
    if panel.unavailable_reason:
        pytest.skip(f"LIVE_FUNDAMENTALS_UNAVAILABLE (application layer): "
                    f"{panel.unavailable_reason}")
    assert panel.is_demo is False
    assert "DEMO" not in panel.data_source
    available = {row.label for row in panel.rows if row.available}
    assert {"总市值", "市盈率 (PE)", "市净率 (PB)"} <= available
