"""
test_current_value_blocked.py — Current API Leak Protection & Verification Tests.
"""

from datetime import datetime
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.quant.data.research_api import ResearchDataAPI
from src.data.contracts.fundamental_data import MetricProvenance


def test_current_api_value_leak_blocked():
    """
    Simulates Current API returning value = 99.0 for current time.
    Historical as_of = 2022-05-01 has valid PIT value = 10.0.
    Backtest / Research query as of 2022-05-01 MUST get 10.0, NEVER 99.0.
    """
    store = RevisionStore()

    # Valid PIT revision in history
    rev_hist = DataRevision(
        record_id="rec_pit",
        symbol="600519.SH",
        field="pe_ttm",
        effective_date="2022-03-31",
        value=10.0,
        provider="tushare_pro",
        available_at=datetime(2022, 4, 28, 9, 0, 0),
        received_at=datetime(2022, 4, 28, 9, 5, 0),
        revision_id="rev_hist",
        dataset_version="ds_v1.0"
    )
    store.add_revision(rev_hist)

    # Current API leak candidate (available_at in 2026 / tagged CURRENT_ONLY)
    rev_current_leak = DataRevision(
        record_id="rec_leak",
        symbol="600519.SH",
        field="pe_ttm",
        effective_date="2022-03-31",
        value=99.0,
        provider="tushare_current_api",
        available_at=datetime(2026, 8, 1, 12, 0, 0), # Future leak!
        received_at=datetime(2026, 8, 1, 12, 0, 0),
        revision_id="rev_leak",
        dataset_version="ds_v2.0",
        provenance=MetricProvenance.CURRENT_ONLY,
        quality_status="CURRENT_ONLY"
    )
    store.add_revision(rev_current_leak)

    mgr = SnapshotManager(revision_store=store)
    api = ResearchDataAPI(snapshot_manager=mgr, revision_store=store)

    # Querying as of 2022-05-01 MUST yield 10.0, NOT 99.0!
    val_past = api.get_metric("600519.SH", "pe_ttm", "2022-03-31", as_of=datetime(2022, 5, 1, 0, 0, 0))
    assert val_past == 10.0
    assert val_past != 99.0


def test_current_only_metric_blocked_for_past_as_of():
    """
    If a metric only exists as CURRENT_ONLY (no historical PIT revision available_at <= as_of exists),
    querying for historical as_of MUST return UNAVAILABLE and block the current value.
    """
    store = RevisionStore()

    rev_current_only = DataRevision(
        record_id="rec_curr_only",
        symbol="000002.SZ",
        field="pe_ttm",
        effective_date="2022-03-31",
        value=35.0,
        provider="current_api",
        available_at=datetime(2026, 8, 1, 0, 0, 0),
        received_at=datetime(2026, 8, 1, 0, 0, 0),
        revision_id="rev_curr",
        dataset_version="ds_v_curr",
        provenance=MetricProvenance.CURRENT_ONLY,
        quality_status="CURRENT_ONLY"
    )
    store.add_revision(rev_current_only)

    mgr = SnapshotManager(revision_store=store)
    api = ResearchDataAPI(snapshot_manager=mgr, revision_store=store)

    val = api.get_metric("000002.SZ", "pe_ttm", "2022-03-31", as_of=datetime(2022, 5, 1))
    assert val == "UNAVAILABLE"
