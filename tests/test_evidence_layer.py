"""
test_evidence_layer.py — EvidenceItem, assembly functions, and the full
API -> Adapter -> Contract -> Validation -> PIT -> Evidence chain.
"""

from datetime import datetime, timedelta

import pytest

from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.contracts.news_announcement import NewsAnnouncementContract
from src.data.providers.news_provider import SyntheticNewsAnnouncementProvider
from src.quant.technical.indicators import compute_moving_average
from src.quant.evidence.evidence_item import (
    EvidenceItem, assemble_market_evidence, assemble_fundamental_evidence,
    assemble_news_evidence, assemble_technical_evidence, detect_duplicate_news,
    compute_evidence_bundle_hash,
)

SYMBOL = "600519.SH"


# --- EvidenceItem structural guarantees ------------------------------------------------------

def test_evidence_item_valid_kinds_construct():
    for kind in ("FACT", "MODEL_OUTPUT"):
        EvidenceItem(
            evidence_id="X-1", category="MARKET", kind=kind, content={"v": 1},
            event_date="2026-08-01", available_at=None, received_at=None,
            source="test", data_origin="SYNTHETIC_DATA",
        )


def test_evidence_item_rejects_ai_interpretation_as_kind():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        EvidenceItem(
            evidence_id="X-1", category="MARKET", kind="AI_INTERPRETATION", content={},
            event_date="2026-08-01", available_at=None, received_at=None,
            source="test", data_origin="SYNTHETIC_DATA",
        )


def test_evidence_item_rejects_unknown_category():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        EvidenceItem(
            evidence_id="X-1", category="RUMOR", kind="FACT", content={},
            event_date="2026-08-01", available_at=None, received_at=None,
            source="test", data_origin="SYNTHETIC_DATA",
        )


def test_evidence_item_rejects_empty_id_and_source():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        EvidenceItem(
            evidence_id="", category="MARKET", kind="FACT", content={},
            event_date="2026-08-01", available_at=None, received_at=None,
            source="test", data_origin="SYNTHETIC_DATA",
        )
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        EvidenceItem(
            evidence_id="X-1", category="MARKET", kind="FACT", content={},
            event_date="2026-08-01", available_at=None, received_at=None,
            source="", data_origin="SYNTHETIC_DATA",
        )


# --- Market / Fundamental assembly -----------------------------------------------------------

def _market(**overrides):
    base = dict(
        symbol=SYMBOL, timestamp=datetime(2026, 8, 1), trading_date="2026-08-01",
        open_price=100.0, high_price=101.0, low_price=99.0, close_price=100.5,
        volume=1000.0, amount=100500.0, adj_factor=1.0, unadjusted_close=100.5,
        trading_status="NORMAL", quality_status="VALID", data_origin="GOLDEN_DATASET",
    )
    base.update(overrides)
    return MarketDataContract(**base)


def test_assemble_market_evidence_valid():
    items = assemble_market_evidence(SYMBOL, [_market()])
    assert len(items) == 1
    assert items[0].kind == "FACT"
    assert items[0].category == "MARKET"
    assert items[0].data_origin == "GOLDEN_DATASET"


def test_assemble_market_evidence_excludes_datatrustgate_invalid():
    bad = _market(quality_status="SUSPECT")
    assert assemble_market_evidence(SYMBOL, [bad]) == []


def test_assemble_market_evidence_symbol_mismatch_fails_closed():
    other = _market(symbol="000001.SZ")
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        assemble_market_evidence(SYMBOL, [other])


def _fundamental(**overrides):
    base = dict(
        symbol=SYMBOL, trade_date="2026-08-01", report_date="2026-06-30",
        announcement_date="2026-07-15", currency="CNY", revenue=1000.0, net_income=100.0,
        eps_annual=1.0, eps_ttm=1.0, book_value_per_share=10.0, operating_cash_flow=200.0,
        shares_outstanding=1000000.0, market_cap=100000000.0, pe_lyr=20.0, pe_ttm=20.0,
        pe_ttm_status="VALID", pb=2.0, pb_status="VALID", dividend_yield_ttm=0.02,
        dividend_yield_status="VALID", roe=0.15, quality_status="VALID",
        available_at=datetime(2026, 7, 15), received_at=datetime(2026, 7, 15, 0, 5),
        data_origin="GOLDEN_DATASET",
    )
    base.update(overrides)
    return FundamentalDataContract(**base)


def test_assemble_fundamental_evidence_pit_filters():
    visible = _fundamental()
    future = _fundamental(available_at=datetime(2026, 12, 1), received_at=datetime(2026, 12, 1))
    items = assemble_fundamental_evidence(SYMBOL, [visible, future], as_of=datetime(2026, 8, 1))
    assert len(items) == 1
    assert items[0].kind == "FACT"


# --- Technical assembly -----------------------------------------------------------------------

def test_assemble_technical_evidence_excludes_insufficient_warmup():
    dates = [f"2026-01-{d:02d}" for d in range(1, 11)]
    prices = [10.0 + d for d in range(10)]
    contracts = compute_moving_average(SYMBOL, dates, prices, window=5)
    items = assemble_technical_evidence(SYMBOL, contracts)
    assert len(items) == 10 - 5 + 1  # only warm_up_satisfied=True entries
    assert all(i.kind == "MODEL_OUTPUT" for i in items)
    assert all(i.category == "TECHNICAL" for i in items)


# --- News dedup / assembly ---------------------------------------------------------------------

def _news(**overrides):
    base = dict(
        source_id="n1", source="Wire A", item_type="NEWS", symbols=[SYMBOL],
        title="贵州茅台发布公告", body_summary="s", source_url=None,
        published_at=datetime(2026, 8, 1), available_at=datetime(2026, 8, 1),
        received_at=datetime(2026, 8, 1, 0, 5),
    )
    base.update(overrides)
    return NewsAnnouncementContract(**base)


def test_detect_duplicate_news_clusters_matching_items():
    a = _news(source_id="a", source="Wire A")
    b = _news(source_id="b", source="Wire A")  # same title/type/symbols/date => same cluster
    c = _news(source_id="c", title="完全不同的标题")
    result = detect_duplicate_news([a, b, c])
    by_id = {i.source_id: i for i in result}
    assert by_id["a"].duplicate_cluster_id == by_id["b"].duplicate_cluster_id
    assert by_id["a"].duplicate_cluster_id is not None
    assert by_id["c"].duplicate_cluster_id is None


def test_assemble_news_evidence_dedup_keeps_one_representative_with_suppressed_count():
    a = _news(source_id="a", received_at=datetime(2026, 8, 1, 0, 5))
    b = _news(source_id="b", received_at=datetime(2026, 8, 1, 0, 10))
    items = assemble_news_evidence(SYMBOL, [a, b], as_of=datetime(2026, 8, 5))
    assert len(items) == 1
    assert items[0].content["suppressed_duplicate_count"] == 1


def test_assemble_news_evidence_pit_filters_late_received():
    visible = _news(source_id="v")
    late = _news(source_id="l", received_at=datetime(2026, 12, 1))
    items = assemble_news_evidence(SYMBOL, [visible, late], as_of=datetime(2026, 8, 5))
    assert len(items) == 1
    assert items[0].content["title"] == visible.title


def test_assemble_news_evidence_conflicting_items_both_kept_not_resolved():
    """Conflicting (not duplicate) items about the same symbol must both survive assembly —
    conflict resolution is a report-generation-time (AI) concern, not an assembly-time one."""
    bullish = _news(source_id="bull", title="业绩超预期")
    bearish = _news(source_id="bear", title="业绩不及预期")
    items = assemble_news_evidence(SYMBOL, [bullish, bearish], as_of=datetime(2026, 8, 5))
    assert len(items) == 2


# --- Evidence Bundle hash -----------------------------------------------------------------------

def test_evidence_bundle_hash_deterministic_and_content_sensitive():
    item = EvidenceItem(
        evidence_id="X-1", category="MARKET", kind="FACT", content={"v": 1},
        event_date="2026-08-01", available_at=None, received_at=None,
        source="test", data_origin="SYNTHETIC_DATA",
    )
    h1 = compute_evidence_bundle_hash([item])
    h2 = compute_evidence_bundle_hash([item])
    assert h1 == h2

    item2 = EvidenceItem(
        evidence_id="X-1", category="MARKET", kind="FACT", content={"v": 2},
        event_date="2026-08-01", available_at=None, received_at=None,
        source="test", data_origin="SYNTHETIC_DATA",
    )
    assert compute_evidence_bundle_hash([item]) != compute_evidence_bundle_hash([item2])


# --- Full chain: API -> Adapter -> Contract -> Validation -> PIT -> Evidence --------------------

def test_full_chain_api_to_adapter_to_contract_to_validation_to_pit_to_evidence():
    provider = SyntheticNewsAnnouncementProvider()
    provider.seed_items(SYMBOL, [
        {  # raw "API response" shape — untrusted dict
            "source_id": "chain_1", "source": "上交所公告", "item_type": "COMPANY_ANNOUNCEMENT",
            "symbols": [SYMBOL], "title": "分红公告", "body_summary": "...",
            "published_at": "2026-08-01T09:00:00", "available_at": "2026-08-01T09:00:00",
            "received_at": "2026-08-01T09:05:00", "announcement_date": "2026-08-01",
        },
        {  # a late-received item that must be excluded by the PIT stage
            "source_id": "chain_2", "source": "上交所公告", "item_type": "COMPANY_ANNOUNCEMENT",
            "symbols": [SYMBOL], "title": "另一条公告", "body_summary": "...",
            "published_at": "2026-08-01T09:00:00", "available_at": "2026-08-01T09:00:00",
            "received_at": "2026-12-01T09:05:00", "announcement_date": "2026-08-01",
        },
    ])

    # API -> Adapter
    page = provider.fetch_news_announcements(SYMBOL, "2026-01-01", "2026-12-31")
    assert len(page.items) == 2  # Adapter already parsed both into canonical Contracts

    # Contract -> Validation -> PIT -> Evidence
    evidence = assemble_news_evidence(SYMBOL, page.items, as_of=datetime(2026, 8, 5))

    assert len(evidence) == 1, "the late-received_at item must be excluded by the PIT stage"
    item = evidence[0]
    assert isinstance(item, EvidenceItem)
    assert item.kind == "FACT"
    assert item.category in ("NEWS", "ANNOUNCEMENT")
    assert item.data_origin == "SYNTHETIC_DATA"
    assert item.source == "上交所公告"

    # The Evidence Bundle is hashable and the hash is stable.
    bundle_hash = compute_evidence_bundle_hash(evidence)
    assert bundle_hash == compute_evidence_bundle_hash(evidence)
