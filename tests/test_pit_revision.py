"""
test_pit_revision.py — Point-in-Time Revision Proof Golden Test.
"""

from datetime import datetime
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore


def test_golden_pit_revision_proof():
    """
    REQUIRED GOLDEN TEST (CEO Directive Section 16):
    Company: Report Date 2022-03-31
    Revision A: value = 10, available_at = 2022-04-28 09:00:00
    Revision B: value = 11, available_at = 2022-05-20 09:00:00

    Tests:
    - as_of = 2022-04-15 00:00:00 -> unavailable (None)
    - as_of = 2022-05-01 00:00:00 -> 10
    - as_of = 2022-05-19 23:59:59 -> 10
    - as_of = 2022-05-21 00:00:00 -> 11
    """
    store = RevisionStore()

    rev_a = DataRevision(
        record_id="rec_eps_001",
        symbol="600519.SH",
        field="eps",
        effective_date="2022-03-31",
        value=10.0,
        provider="tushare_pro",
        available_at=datetime(2022, 4, 28, 9, 0, 0),
        received_at=datetime(2022, 4, 28, 9, 5, 0),
        revision_id="rev_a",
        dataset_version="ds_v1.0"
    )
    store.add_revision(rev_a)

    rev_b = DataRevision(
        record_id="rec_eps_002",
        symbol="600519.SH",
        field="eps",
        effective_date="2022-03-31",
        value=11.0,
        provider="tushare_pro",
        available_at=datetime(2022, 5, 20, 9, 0, 0),
        received_at=datetime(2022, 5, 20, 9, 5, 0),
        revision_id="rev_b",
        dataset_version="ds_v1.1"
    )
    store.add_revision(rev_b)

    # 1. as_of = 2022-04-15 -> Unavailable (None)
    res_0415 = store.query_pit("600519.SH", "eps", "2022-03-31", datetime(2022, 4, 15, 0, 0, 0))
    assert res_0415 is None

    # 2. as_of = 2022-05-01 -> 10.0
    res_0501 = store.query_pit("600519.SH", "eps", "2022-03-31", datetime(2022, 5, 1, 0, 0, 0))
    assert res_0501 is not None
    assert res_0501.value == 10.0
    assert res_0501.revision_id == "rev_a"

    # 3. as_of = 2022-05-19 -> 10.0
    res_0519 = store.query_pit("600519.SH", "eps", "2022-03-31", datetime(2022, 5, 19, 23, 59, 59))
    assert res_0519 is not None
    assert res_0519.value == 10.0
    assert res_0519.revision_id == "rev_a"

    # 4. as_of = 2022-05-21 -> 11.0
    res_0521 = store.query_pit("600519.SH", "eps", "2022-03-31", datetime(2022, 5, 21, 0, 0, 0))
    assert res_0521 is not None
    assert res_0521.value == 11.0
    assert res_0521.revision_id == "rev_b"
