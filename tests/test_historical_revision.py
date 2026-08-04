"""
test_historical_revision.py — Tests verifying price adjustments & fundamental restatement revisions across datasets.
"""

from datetime import datetime
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore


def test_historical_restatement_non_deletion():
    store = RevisionStore()

    # Original fundamental report
    v1 = DataRevision(
        record_id="rec_v1",
        symbol="600000.SH",
        field="revenue",
        effective_date="2021-12-31",
        value=100000.0,
        provider="tushare",
        available_at=datetime(2022, 3, 30, 9, 0),
        received_at=datetime(2022, 3, 30, 9, 0),
        revision_id="r1",
        dataset_version="ds_v1"
    )
    store.add_revision(v1)

    # Restatement 6 months later
    v2 = DataRevision(
        record_id="rec_v2",
        symbol="600000.SH",
        field="revenue",
        effective_date="2021-12-31",
        value=105000.0,
        provider="tushare",
        available_at=datetime(2022, 9, 30, 9, 0),
        received_at=datetime(2022, 9, 30, 9, 0),
        revision_id="r2",
        dataset_version="ds_v2"
    )
    store.add_revision(v2)

    # Querying past as_of (2022-05-01) MUST see v1 (100000.0)
    pit_may = store.query_pit("600000.SH", "revenue", "2021-12-31", datetime(2022, 5, 1))
    assert pit_may.value == 100000.0

    # Querying present as_of (2022-10-01) sees restated v2 (105000.0)
    pit_oct = store.query_pit("600000.SH", "revenue", "2021-12-31", datetime(2022, 10, 1))
    assert pit_oct.value == 105000.0
