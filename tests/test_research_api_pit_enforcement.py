"""
test_research_api_pit_enforcement.py — Audit test verifying ResearchDataAPI strictly filters future data.
"""

from datetime import datetime
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.quant.data.research_api import ResearchDataAPI


def test_research_api_filters_future_available_data():
    store = RevisionStore()
    
    # Revision A: available in April
    r_past = DataRevision(
        record_id="p1", symbol="600519.SH", field="close", effective_date="2022-04-15",
        value=1600.0, provider="tushare", available_at=datetime(2022, 4, 15, 15, 0),
        received_at=datetime(2022, 4, 15, 15, 0), revision_id="r1", dataset_version="ds_v1"
    )
    store.add_revision(r_past)

    # Revision B: available in May
    r_future = DataRevision(
        record_id="p2", symbol="600519.SH", field="close", effective_date="2022-05-15",
        value=1650.0, provider="tushare", available_at=datetime(2022, 5, 15, 15, 0),
        received_at=datetime(2022, 5, 15, 15, 0), revision_id="r2", dataset_version="ds_v1"
    )
    store.add_revision(r_future)

    mgr = SnapshotManager(revision_store=store)
    api = ResearchDataAPI(snapshot_manager=mgr, revision_store=store)

    # Querying as of May 1st (before Revision B becomes available)
    prices = api.get_prices(["600519.SH"], "2022-04-01", "2022-05-31", as_of=datetime(2022, 5, 1))

    # Revision B (available May 15) MUST be filtered out!
    assert len(prices) == 1
    assert prices[0].effective_date == "2022-04-15"
    assert prices[0].value == 1600.0
