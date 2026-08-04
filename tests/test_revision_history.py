"""
test_revision_history.py — Tests tracking revision history & audit trail.
"""

from datetime import datetime
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore


def test_revision_history_audit_trail():
    store = RevisionStore()

    r1 = DataRevision(
        record_id="rec_1",
        symbol="000001.SZ",
        field="net_income",
        effective_date="2022-03-31",
        value=50000000.0,
        provider="tushare",
        available_at=datetime(2022, 4, 15, 9, 0),
        received_at=datetime(2022, 4, 15, 9, 5),
        revision_id="rev_1",
        dataset_version="ds_v1"
    )
    store.add_revision(r1)

    r2 = DataRevision(
        record_id="rec_2",
        symbol="000001.SZ",
        field="net_income",
        effective_date="2022-03-31",
        value=52000000.0, # Restated
        provider="tushare",
        available_at=datetime(2022, 6, 1, 9, 0),
        received_at=datetime(2022, 6, 1, 9, 5),
        revision_id="rev_2",
        dataset_version="ds_v2"
    )
    store.add_revision(r2)

    history = store.get_revision_history("000001.SZ", "net_income", "2022-03-31")
    assert len(history) == 2
    assert history[0].revision_id == "rev_1"
    assert history[0].is_current is False
    assert history[1].revision_id == "rev_2"
    assert history[1].is_current is True
    assert history[1].supersedes_revision_id == "rev_1"
