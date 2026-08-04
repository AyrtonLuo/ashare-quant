"""
test_unavailable_pit_data.py — Tests verifying failure policy on missing PIT data (Section 29).
"""

from datetime import datetime
from src.data.revision.revision_store import RevisionStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.quant.data.research_api import ResearchDataAPI


def test_missing_pit_data_returns_unavailable():
    """
    Failure Policy (CEO Directive Section 29):
    If data cannot be proven legally available at as_of=T,
    MUST return UNAVAILABLE / None.
    MUST NOT fillna(0), guess, fallback to current API value, or use future revision.
    """
    store = RevisionStore()
    mgr = SnapshotManager(revision_store=store)
    api = ResearchDataAPI(snapshot_manager=mgr, revision_store=store)

    # Querying metric for non-existent or future available data
    result = api.get_metric("600519.SH", "pb", "2022-03-31", as_of=datetime(2022, 4, 15))
    
    assert result == "UNAVAILABLE"
    assert result != 0
    assert result != 0.0
    assert result is not None  # Explicit UNAVAILABLE signal
