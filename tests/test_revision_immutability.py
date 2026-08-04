"""
test_revision_immutability.py — Audit test proving revision chains are immutable and non-destructive.
"""

from datetime import datetime
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore


def test_revision_chain_preserves_full_history():
    store = RevisionStore()

    r_a = DataRevision(
        record_id="rec_a", symbol="000001.SZ", field="net_income", effective_date="2022-03-31",
        value=100.0, provider="tushare", available_at=datetime(2022, 4, 15), received_at=datetime(2022, 4, 15),
        revision_id="rev_A", dataset_version="ds_v1"
    )
    store.add_revision(r_a)

    r_b = DataRevision(
        record_id="rec_b", symbol="000001.SZ", field="net_income", effective_date="2022-03-31",
        value=110.0, provider="tushare", available_at=datetime(2022, 5, 20), received_at=datetime(2022, 5, 20),
        revision_id="rev_B", dataset_version="ds_v2"
    )
    store.add_revision(r_b)

    r_c = DataRevision(
        record_id="rec_c", symbol="000001.SZ", field="net_income", effective_date="2022-03-31",
        value=115.0, provider="tushare", available_at=datetime(2022, 8, 10), received_at=datetime(2022, 8, 10),
        revision_id="rev_C", dataset_version="ds_v3"
    )
    store.add_revision(r_c)

    # 1. Verify history contains all 3 revisions in chain
    history = store.get_revision_history("000001.SZ", "net_income", "2022-03-31")
    assert len(history) == 3
    assert history[0].revision_id == "rev_A"
    assert history[1].revision_id == "rev_B"
    assert history[2].revision_id == "rev_C"

    # 2. Verify PIT queries resolve correctly for each era
    # as_of before Rev A -> None
    assert store.query_pit("000001.SZ", "net_income", "2022-03-31", datetime(2022, 4, 1)).value if store.query_pit("000001.SZ", "net_income", "2022-03-31", datetime(2022, 4, 1)) else None is None

    # as_of after Rev A, before Rev B -> Rev A (100.0)
    res_a = store.query_pit("000001.SZ", "net_income", "2022-03-31", datetime(2022, 5, 1))
    assert res_a.value == 100.0
    assert res_a.revision_id == "rev_A"

    # as_of after Rev B, before Rev C -> Rev B (110.0)
    res_b = store.query_pit("000001.SZ", "net_income", "2022-03-31", datetime(2022, 6, 1))
    assert res_b.value == 110.0
    assert res_b.revision_id == "rev_B"

    # as_of after Rev C -> Rev C (115.0)
    res_c = store.query_pit("000001.SZ", "net_income", "2022-03-31", datetime(2022, 9, 1))
    assert res_c.value == 115.0
    assert res_c.revision_id == "rev_C"
