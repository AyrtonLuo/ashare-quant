"""
test_pit_gate_news.py — PITGate.filter_pit_news_announcements() historical PIT filtering.

published_at <= as_of AND received_at <= as_of — the directive's own explicit formula, reusing
the existing PIT architecture (same dual-cutoff pattern as filter_pit_fundamentals/
filter_pit_corporate_actions), not a new philosophy.
"""

from datetime import datetime

from src.data.contracts.news_announcement import NewsAnnouncementContract
from src.data.validation.pit_gate import PITGate

SYMBOL = "600519.SH"
CUTOFF = datetime(2026, 8, 5, 12, 0)


def _news(published_at, received_at):
    return NewsAnnouncementContract(
        source_id="n1", source="Test Wire", item_type="NEWS", symbols=[SYMBOL],
        title="t", body_summary="s", source_url=None,
        published_at=published_at, available_at=published_at, received_at=received_at,
    )


def test_normal_pit_visible_when_both_before_cutoff():
    item = _news(datetime(2026, 8, 1), datetime(2026, 8, 1, 0, 5))
    assert PITGate.filter_pit_news_announcements([item], CUTOFF) == [item]


def test_late_published_at_excluded():
    item = _news(datetime(2026, 8, 6), datetime(2026, 8, 1))
    assert PITGate.filter_pit_news_announcements([item], CUTOFF) == []


def test_late_received_at_excluded():
    item = _news(datetime(2026, 8, 1), datetime(2026, 8, 6))
    assert PITGate.filter_pit_news_announcements([item], CUTOFF) == []


def test_both_late_excluded():
    item = _news(datetime(2026, 8, 6), datetime(2026, 8, 7))
    assert PITGate.filter_pit_news_announcements([item], CUTOFF) == []


def test_cutoff_equality_visible():
    item = _news(CUTOFF, CUTOFF)
    assert PITGate.filter_pit_news_announcements([item], CUTOFF) == [item]


def test_missing_received_at_excluded_fails_closed():
    item = _news(datetime(2026, 8, 1), None)
    assert PITGate.filter_pit_news_announcements([item], CUTOFF) == []


def test_missing_published_at_excluded_fails_closed():
    """published_at is a required (non-Optional) contract field, so None can only occur via a
    type-hint-violating construction — the gate must still refuse to treat it as visible."""
    item = _news(None, datetime(2026, 8, 1))
    assert PITGate.filter_pit_news_announcements([item], CUTOFF) == []
