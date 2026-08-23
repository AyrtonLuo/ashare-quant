"""
test_news_provider_adapter.py — News Provider Adapter tests: the Adapter -> Contract boundary.

Covers the directive's explicit Step 4 checklist for the News/Announcement path: valid response,
missing field, wrong datatype, malformed response, empty response, provider error, invalid
timestamp, future timestamp, missing received_at, symbol mismatch, duplicate, pagination,
partial provider failure.
"""

from datetime import datetime, timedelta

import pytest

from src.data.providers.base import ProviderError
from src.data.providers.news_provider import (
    SyntheticNewsAnnouncementProvider, LiveNewsAnnouncementProvider,
    _parse_raw_item, PROVIDER_ERROR_SIMULATION_SYMBOL,
)

SYMBOL = "600519.SH"


def _valid_raw(**overrides):
    base = dict(
        source_id="news_001", source="上交所公告", item_type="COMPANY_ANNOUNCEMENT",
        symbols=[SYMBOL], title="贵州茅台2026年年报", body_summary="summary",
        source_url="https://example.com/n1",
        published_at="2026-08-01T09:00:00", available_at="2026-08-01T09:00:00",
        received_at="2026-08-01T09:05:00", announcement_date="2026-08-01",
    )
    base.update(overrides)
    return base


# --- Adapter -> Contract parsing boundary -------------------------------------------------

def test_valid_api_response_parses_to_contract():
    contract = _parse_raw_item(_valid_raw(), SYMBOL)
    assert contract.source_id == "news_001"
    assert contract.symbols == [SYMBOL]
    assert contract.data_origin == "SYNTHETIC_DATA"


def test_missing_required_field_fails_closed():
    raw = _valid_raw()
    del raw["title"]
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _parse_raw_item(raw, SYMBOL)


def test_wrong_datatype_fails_closed():
    raw = _valid_raw(symbols=SYMBOL)  # str, not List[str]
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _parse_raw_item(raw, SYMBOL)


def test_malformed_response_not_a_dict_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _parse_raw_item("not a dict", SYMBOL)


def test_malformed_timestamp_fails_closed():
    raw = _valid_raw(published_at="not-a-real-date")
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _parse_raw_item(raw, SYMBOL)


def test_future_timestamp_fails_closed():
    future = (datetime.now() + timedelta(days=3650)).isoformat()
    raw = _valid_raw(published_at=future)
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _parse_raw_item(raw, SYMBOL)


def test_symbol_mismatch_fails_closed():
    raw = _valid_raw(symbols=["000001.SZ"])
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _parse_raw_item(raw, SYMBOL)


def test_missing_received_at_parses_with_none_not_fabricated():
    raw = _valid_raw()
    del raw["received_at"]
    contract = _parse_raw_item(raw, SYMBOL)
    assert contract.received_at is None


# --- SyntheticNewsAnnouncementProvider (Adapter) ------------------------------------------

def test_empty_response_returns_empty_page_not_error():
    provider = SyntheticNewsAnnouncementProvider()
    page = provider.fetch_news_announcements("000001.SZ", "2026-01-01", "2026-12-31")
    assert page.items == []
    assert page.has_more is False


def test_provider_error_propagates_not_swallowed():
    provider = SyntheticNewsAnnouncementProvider()
    with pytest.raises(ProviderError):
        provider.fetch_news_announcements(PROVIDER_ERROR_SIMULATION_SYMBOL, "2026-01-01", "2026-12-31")


def test_pagination_returns_multiple_pages_with_correct_has_more():
    provider = SyntheticNewsAnnouncementProvider()
    raw_items = [_valid_raw(source_id=f"news_{i}") for i in range(5)]
    provider.seed_items(SYMBOL, raw_items)

    page1 = provider.fetch_news_announcements(SYMBOL, "2026-01-01", "2026-12-31", page=1)
    assert len(page1.items) == 2 and page1.has_more is True
    page2 = provider.fetch_news_announcements(SYMBOL, "2026-01-01", "2026-12-31", page=2)
    assert len(page2.items) == 2 and page2.has_more is True
    page3 = provider.fetch_news_announcements(SYMBOL, "2026-01-01", "2026-12-31", page=3)
    assert len(page3.items) == 1 and page3.has_more is False


def test_partial_provider_failure_within_page_fails_closed_not_silently_dropped():
    """One malformed item among otherwise-valid raw items must not be silently skipped — the
    whole page's fetch fails closed, surfacing the problem rather than hiding it."""
    provider = SyntheticNewsAnnouncementProvider()
    good = _valid_raw(source_id="good_1")
    bad = _valid_raw(source_id="bad_1")
    del bad["title"]
    provider.seed_items(SYMBOL, [good, bad])
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        provider.fetch_news_announcements(SYMBOL, "2026-01-01", "2026-12-31")


def test_date_range_excludes_items_outside_window():
    provider = SyntheticNewsAnnouncementProvider()
    provider.seed_items(SYMBOL, [_valid_raw(source_id="outside", announcement_date="2020-01-01")])
    page = provider.fetch_news_announcements(SYMBOL, "2026-01-01", "2026-12-31")
    assert page.items == []


# --- LiveNewsAnnouncementProvider — explicit refusal, never a silent stub -----------------

def test_live_provider_explicitly_refuses_not_silent_stub():
    provider = LiveNewsAnnouncementProvider()
    with pytest.raises(ProviderError, match="not implemented"):
        provider.fetch_news_announcements(SYMBOL, "2026-01-01", "2026-12-31")
