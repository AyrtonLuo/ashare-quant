"""
test_news_announcement_contract.py — NewsAnnouncementContract structural (Contract-stage) tests.

AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md / API & Data Contract Implementation Directive.
"""

from datetime import datetime

import pytest

from src.data.contracts.news_announcement import NewsAnnouncementContract

SYMBOL = "600519.SH"


def _valid(**overrides):
    base = dict(
        source_id="news_001", source="上交所公告", item_type="COMPANY_ANNOUNCEMENT",
        symbols=[SYMBOL], title="贵州茅台2026年年报", body_summary="summary text", source_url=None,
        published_at=datetime(2026, 8, 1, 9, 0),
        available_at=datetime(2026, 8, 1, 9, 0), received_at=datetime(2026, 8, 1, 9, 5),
    )
    base.update(overrides)
    return NewsAnnouncementContract(**base)


def test_valid_construction():
    contract = _valid()
    assert contract.source_id == "news_001"
    assert contract.data_origin == "SYNTHETIC_DATA"


def test_empty_source_id_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _valid(source_id="")


def test_empty_source_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _valid(source="")


def test_empty_title_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _valid(title="")


def test_empty_symbols_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _valid(symbols=[])


def test_unknown_item_type_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _valid(item_type="RUMOR")


def test_missing_received_at_constructs_with_none_not_fabricated():
    contract = _valid(received_at=None)
    assert contract.received_at is None
