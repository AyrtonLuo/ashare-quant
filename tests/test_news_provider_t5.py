"""
test_news_provider_t5.py — real company announcements (Terminal step T5).

Offline tests run against a local HTTP stub, so parsing, symbol attribution and every failure
path are deterministic and network-free. One live test at the end calls the public endpoint and
is skipped — never failed — when the network is unavailable.

The property that matters most: a fabricated news item is the most misleading thing this product
could show, so there is no synthetic fallback anywhere on this path.
"""

import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.app import terminal_application as terminal
from src.data.providers.base import NewsAnnouncementProvider, ProviderError
from src.data.providers.eastmoney_news_provider import (
    EASTMONEY_NEWS_PROVIDER_ID,
    EASTMONEY_SOURCE_NAME,
    EastMoneyAnnouncementProvider,
)
from src.data.validation.gate import DataTrustGate

SYMBOL = "600519.SH"
CODE = "600519"


def _entry(art="AN20260814182799440", title="贵州茅台:关于召开业绩说明会的公告",
           notice_date="2026-08-15 00:00:00", codes=None):
    return {
        "art_code": art, "title": title, "title_ch": title,
        "notice_date": notice_date, "display_time": "2026-08-14 20:41:29:380",
        "codes": codes if codes is not None else [
            {"stock_code": CODE, "short_name": "贵州茅台", "market_code": "1"}],
        "columns": [{"column_code": "001002008", "column_name": "其他"}],
    }


def _body(entries=None, total=100):
    return json.dumps({
        "success": True, "error": None,
        "data": {"list": entries if entries is not None else [_entry()],
                 "page_index": 1, "page_size": 20, "total_hits": total},
    })


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
    yield f"http://127.0.0.1:{server.server_port}/api/security/ann"
    server.shutdown()
    server.server_close()


def _provider(url):
    return EastMoneyAnnouncementProvider(base_url=url)


def _fetch(url, symbol=SYMBOL, start="2026-01-01", end="2026-12-31"):
    return _provider(url).fetch_news_announcements(symbol, start, end)


# --- interface / dependencies -----------------------------------------------------------------

def test_implements_the_existing_news_provider_abc(stub_url):
    provider = _provider(stub_url)
    assert isinstance(provider, NewsAnnouncementProvider)
    assert provider.provider_id == EASTMONEY_NEWS_PROVIDER_ID
    assert provider.provider_version


def test_the_news_feed_declares_its_own_source_label(stub_url):
    """Four feeds — quote, history, fundamentals, news — four source labels. Never one claim."""
    label = _provider(stub_url).source_label
    assert EASTMONEY_SOURCE_NAME in label
    assert EASTMONEY_NEWS_PROVIDER_ID in label


def test_no_new_third_party_dependency():
    import inspect
    import src.data.providers.eastmoney_news_provider as module
    source = inspect.getsource(module)
    for dependency in ("import requests", "import httpx", "import pandas", "import akshare",
                       "import feedparser", "BeautifulSoup"):
        assert dependency not in source


# --- happy path -------------------------------------------------------------------------------

def test_a_live_shaped_payload_parses_into_real_provider_announcements(stub_url):
    _StubState.body = _body()
    page = _fetch(stub_url)

    assert len(page.items) == 1
    item = page.items[0]
    assert item.data_origin == "REAL_PROVIDER"
    assert item.item_type == "COMPANY_ANNOUNCEMENT"
    assert item.title == "贵州茅台:关于召开业绩说明会的公告"
    assert item.published_at == datetime(2026, 8, 15)
    assert item.source == EASTMONEY_SOURCE_NAME
    assert item.symbols == [SYMBOL]
    assert item.source_id == "AN20260814182799440"


def test_every_item_carries_a_link_to_the_original_document(stub_url):
    _StubState.body = _body()
    item = _fetch(stub_url).items[0]
    assert item.source_url.startswith("https://data.eastmoney.com/notices/detail/600519/")
    assert item.source_url.endswith(".html")


def test_every_item_passes_the_trust_gate(stub_url):
    _StubState.body = _body()
    for item in _fetch(stub_url).items:
        is_valid, errors = DataTrustGate.validate_news_announcement(item)
        assert is_valid, errors


def test_items_are_announcements_never_labelled_as_press_news(stub_url):
    """These are 公告. Calling them NEWS would claim press coverage the source does not provide."""
    _StubState.body = _body()
    assert all(i.item_type == "COMPANY_ANNOUNCEMENT" for i in _fetch(stub_url).items)


def test_pagination_is_reported(stub_url):
    _StubState.body = _body(total=100)
    assert _fetch(stub_url).has_more is True
    _StubState.body = _body(total=1)
    assert _fetch(stub_url, symbol="000001.SZ").has_more is False


# --- nothing is invented ---------------------------------------------------------------------------

def test_body_summary_is_left_empty_never_paraphrased_or_generated(stub_url):
    """This endpoint carries no body text. Writing one would be fabricating a news fact."""
    _StubState.body = _body()
    assert _fetch(stub_url).items[0].body_summary == ""


def test_relevance_is_deterministic_and_rule_based_never_judged(stub_url):
    _StubState.body = _body()
    assert _fetch(stub_url).items[0].relevance_score == 1.0


def test_symbol_association_comes_from_the_payload_not_from_the_query(stub_url):
    """An item that does not name the company is EXCLUDED rather than attributed to it just
    because we asked about that symbol."""
    _StubState.body = _body([
        _entry(art="A1", codes=[{"stock_code": "000002", "short_name": "万科A"}]),
        _entry(art="A2"),
    ])
    items = _fetch(stub_url).items
    assert [i.source_id for i in items] == ["A2"]


def test_an_item_with_no_code_list_is_excluded(stub_url):
    _StubState.body = _body([_entry(art="A1", codes=[]), _entry(art="A2")])
    assert [i.source_id for i in _fetch(stub_url).items] == ["A2"]


def test_the_vendor_category_is_dropped_rather_than_squeezed_into_the_summary(stub_url):
    """NewsAnnouncementContract has no category field, and body_summary means "an excerpt
    captured at ingest" — not a taxonomy label."""
    _StubState.body = _body()
    item = _fetch(stub_url).items[0]
    assert "其他" not in item.body_summary
    assert item.body_summary == ""


# --- date window -----------------------------------------------------------------------------------

def test_items_outside_the_requested_window_are_excluded(stub_url):
    _StubState.body = _body([
        _entry(art="OLD", notice_date="2025-01-01 00:00:00"),
        _entry(art="IN", notice_date="2026-08-15 00:00:00"),
    ])
    page = _provider(stub_url).fetch_news_announcements(SYMBOL, "2026-01-01", "2026-12-31")
    assert [i.source_id for i in page.items] == ["IN"]


# --- fail-closed paths ------------------------------------------------------------------------------

def test_a_missing_data_block_is_refused(stub_url):
    _StubState.body = json.dumps({"success": True})
    with pytest.raises(ProviderError, match="no data block"):
        _fetch(stub_url)


def test_a_missing_list_is_refused(stub_url):
    _StubState.body = json.dumps({"data": {"total_hits": 0}})
    with pytest.raises(ProviderError, match="no list"):
        _fetch(stub_url)


def test_an_empty_list_yields_no_items_without_error(stub_url):
    """A company with no recent announcements is a valid answer, not a failure."""
    _StubState.body = _body([], total=0)
    page = _fetch(stub_url)
    assert page.items == [] and page.has_more is False


def test_an_entry_missing_its_title_or_id_is_refused(stub_url):
    _StubState.body = _body([{"art_code": "A1", "codes": [{"stock_code": CODE}]}])
    with pytest.raises(ProviderError, match="missing art_code or title"):
        _fetch(stub_url)


def test_an_unparseable_notice_date_is_refused(stub_url):
    _StubState.body = _body([_entry(notice_date="not-a-date")])
    with pytest.raises(ProviderError, match="unparseable notice_date"):
        _fetch(stub_url)


def test_a_missing_notice_date_is_refused(stub_url):
    entry = _entry()
    del entry["notice_date"]
    _StubState.body = _body([entry])
    with pytest.raises(ProviderError, match="has no notice_date"):
        _fetch(stub_url)


def test_malformed_json_is_refused(stub_url):
    _StubState.body = "not json"
    with pytest.raises(ProviderError, match="not valid JSON"):
        _fetch(stub_url)


def test_an_http_error_is_reported(stub_url):
    _StubState.status, _StubState.body = 503, "{}"
    with pytest.raises(ProviderError, match="HTTP 503"):
        _fetch(stub_url)


def test_an_unreachable_endpoint_is_reported():
    provider = EastMoneyAnnouncementProvider(
        base_url="http://127.0.0.1:1/api/security/ann", timeout_seconds=2.0)
    with pytest.raises(ProviderError, match="could not reach"):
        provider.fetch_news_announcements(SYMBOL, "2026-01-01", "2026-12-31")


@pytest.mark.parametrize("symbol", ["600519", "600519.XX", "ABCDEF.SH", ""])
def test_an_unmappable_symbol_is_refused_rather_than_guessed(stub_url, symbol):
    """A guessed code returns real announcements for the WRONG company."""
    with pytest.raises(ProviderError):
        _fetch(stub_url, symbol=symbol)


def test_an_invalid_page_is_refused(stub_url):
    with pytest.raises(ProviderError, match="invalid page number"):
        _provider(stub_url).fetch_news_announcements(SYMBOL, "", "", page=0)


def test_a_repeat_request_is_served_from_cache(stub_url):
    _StubState.body = _body()
    provider = _provider(stub_url)
    provider.fetch_news_announcements(SYMBOL, "2026-01-01", "2026-12-31")
    _StubState.last_path = None
    provider.fetch_news_announcements(SYMBOL, "2026-01-01", "2026-12-31")
    assert _StubState.last_path is None


# --- the Terminal panel: REAL / DEMO isolation ---------------------------------------------------------

def test_demo_mode_has_no_news_source_and_never_synthesises_one():
    panel = terminal.get_news_panel(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    assert panel.items == ()
    assert panel.is_demo is True
    assert "不会用合成新闻填充" in panel.unavailable_reason
    assert terminal._news_provider(terminal.QUOTE_SOURCE_DEMO) is None


def test_real_mode_uses_the_live_announcement_provider():
    provider = terminal._news_provider(terminal.QUOTE_SOURCE_REAL)
    assert isinstance(provider, EastMoneyAnnouncementProvider)


def test_an_unknown_source_mode_has_no_news_provider():
    with pytest.raises(terminal.TerminalError, match="未知的数据源模式"):
        terminal._news_provider("SOMETHING_ELSE")


def test_a_failed_real_fetch_reports_the_failure_and_never_falls_back(monkeypatch):
    class _Failing:
        source_label = "stub"

        def fetch_news_announcements(self, *args, **kwargs):
            raise ProviderError("stub", "模拟：公告源不可用")

    monkeypatch.setattr(terminal, "_news_provider", lambda source=None: _Failing())
    panel = terminal.get_news_panel(SYMBOL, terminal.QUOTE_SOURCE_REAL)
    assert panel.items == ()
    assert "公告源不可用" in panel.unavailable_reason
    assert panel.is_demo is False          # a REAL failure never becomes a DEMO answer


def test_the_panel_declares_its_own_source_separate_from_the_other_feeds():
    demo = terminal.get_news_panel(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    quote = terminal.get_quote_view(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    assert demo.data_source
    # The news panel names a news source; it must not inherit the quote's label verbatim.
    assert demo.data_source != quote.data_source or demo.is_demo


# --- the live endpoint ----------------------------------------------------------------------------------

@pytest.mark.real_provider
def test_live_announcements_from_the_public_endpoint():
    """API → Adapter → Contract → Validation, against the real endpoint."""
    provider = EastMoneyAnnouncementProvider()
    try:
        page = provider.fetch_news_announcements(SYMBOL, "2020-01-01", "2030-12-31")
    except ProviderError as e:
        pytest.skip(f"LIVE_NEWS_UNAVAILABLE: {e}")

    assert page.items, "expected at least one real announcement"
    for item in page.items:
        assert item.data_origin == "REAL_PROVIDER"
        assert item.title and item.source_url
        assert item.symbols == [SYMBOL]
        is_valid, errors = DataTrustGate.validate_news_announcement(item)
        assert is_valid, errors

    panel = terminal.get_news_panel(SYMBOL, terminal.QUOTE_SOURCE_REAL)
    assert panel.is_demo is False
    assert panel.items, panel.unavailable_reason
    assert all(i.source_url for i in panel.items)
    assert all(i.summary == "" for i in panel.items)   # nothing was generated
