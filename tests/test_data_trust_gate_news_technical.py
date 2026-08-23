"""
test_data_trust_gate_news_technical.py — DataTrustGate.validate_news_announcement() /
validate_technical_indicator() (Validation stage of the API data pipeline).
"""

from datetime import datetime, timedelta

from src.data.contracts.news_announcement import NewsAnnouncementContract
from src.data.contracts.derived import DerivedDataContract
from src.data.validation.gate import DataTrustGate

SYMBOL = "600519.SH"


def _news(**overrides):
    base = dict(
        source_id="n1", source="Test Wire", item_type="NEWS", symbols=[SYMBOL],
        title="t", body_summary="s", source_url=None,
        published_at=datetime(2026, 8, 1), available_at=datetime(2026, 8, 1),
        received_at=datetime(2026, 8, 1, 0, 5), relevance_score=0.9,
    )
    base.update(overrides)
    return NewsAnnouncementContract(**base)


def test_news_valid_passes():
    is_valid, errors = DataTrustGate.validate_news_announcement(_news())
    assert is_valid is True
    assert errors == []


def test_news_missing_received_at_fails():
    is_valid, errors = DataTrustGate.validate_news_announcement(_news(received_at=None))
    assert is_valid is False
    assert any("received_at" in e for e in errors)


def test_news_missing_available_at_fails():
    is_valid, errors = DataTrustGate.validate_news_announcement(_news(available_at=None))
    assert is_valid is False
    assert any("available_at" in e for e in errors)


def test_news_future_published_at_fails():
    future = datetime.now() + timedelta(days=3650)
    is_valid, errors = DataTrustGate.validate_news_announcement(
        _news(published_at=future, available_at=future, received_at=future)
    )
    assert is_valid is False
    assert any("future" in e for e in errors)


def test_news_received_before_published_fails():
    is_valid, errors = DataTrustGate.validate_news_announcement(
        _news(published_at=datetime(2026, 8, 5), received_at=datetime(2026, 8, 1))
    )
    assert is_valid is False
    assert any("before" in e for e in errors)


def test_news_relevance_score_out_of_range_fails():
    is_valid, errors = DataTrustGate.validate_news_announcement(_news(relevance_score=1.5))
    assert is_valid is False
    assert any("relevance_score" in e for e in errors)


def _indicator(**overrides):
    base = dict(
        symbol=SYMBOL, metric_name="MA_20", calculated_value=100.0, derived_at=datetime.now(),
        formula_version="1.0", input_data_ids=["x"], input_as_of=datetime.now(),
        quality_status="VALID", effective_date="2026-08-01", parameters={"window": 20},
        input_price_basis="PIT_ADJUSTED", lookback_window=20, warm_up_satisfied=True,
    )
    base.update(overrides)
    return DerivedDataContract(**base)


def test_technical_valid_passes():
    is_valid, errors = DataTrustGate.validate_technical_indicator(_indicator())
    assert is_valid is True


def test_technical_insufficient_warmup_consistent_state_passes():
    is_valid, errors = DataTrustGate.validate_technical_indicator(_indicator(
        calculated_value=None, quality_status="INSUFFICIENT_WARM_UP", warm_up_satisfied=False,
    ))
    assert is_valid is True


def test_technical_warmup_true_but_value_none_fails():
    is_valid, errors = DataTrustGate.validate_technical_indicator(_indicator(
        calculated_value=None, warm_up_satisfied=True,
    ))
    assert is_valid is False
    assert any("inconsistent" in e for e in errors)


def test_technical_missing_effective_date_fails():
    is_valid, errors = DataTrustGate.validate_technical_indicator(_indicator(effective_date=None))
    assert is_valid is False
    assert any("effective_date" in e for e in errors)
