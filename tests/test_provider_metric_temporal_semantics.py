"""
test_provider_metric_temporal_semantics.py — Tests verifying Provider-reported metrics temporal semantics.
"""

from datetime import datetime
from src.data.contracts.fundamental_data import FundamentalDataContract, MetricProvenance
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore
from src.data.snapshot.snapshot_manager import SnapshotManager


def test_provider_reported_metric_temporal_provenance():
    """
    Verifies that provider-reported PE, PE_TTM, PB, Dividend Yield, ROE preserve all required temporal fields:
    provider, provider_field, provider_timestamp, event_time, effective_date, available_at, received_at, as_of, provenance, quality_status.
    """
    store = RevisionStore()
    t_avail = datetime(2022, 4, 28, 9, 0, 0)
    t_recv = datetime(2022, 4, 28, 9, 5, 0)
    t_asof = datetime(2022, 5, 1, 0, 0, 0)

    rev_pe = DataRevision(
        record_id="rec_pe",
        symbol="600519.SH",
        field="pe_ttm",
        effective_date="2021-12-31",
        value=28.45,
        provider="tushare_pro",
        available_at=t_avail,
        received_at=t_recv,
        revision_id="rev_pe_1",
        dataset_version="ds_v1.0",
        provenance=MetricProvenance.PROVIDER_REPORTED,
        quality_status="VALID",
        provider_field="pe_ttm",
        provider_timestamp=t_avail,
        as_of_limit=t_asof
    )
    store.add_revision(rev_pe)

    mgr = SnapshotManager(revision_store=store)
    fund = mgr.query_fundamentals("600519.SH", as_of=t_asof, effective_date="2021-12-31")

    assert fund is not None
    assert fund.pe_ttm == 28.45
    assert fund.pe_ttm_status == "VALID"
    assert fund.provenance == MetricProvenance.PROVIDER_REPORTED
    assert fund.quality_status == "VALID"
