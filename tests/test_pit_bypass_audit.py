"""
test_pit_bypass_audit.py — Audit test proving that un-gated data queries without as_of or snapshot_id are rejected.
"""

import pytest
from datetime import datetime
from src.quant.data.research_api import ResearchDataAPI
from src.data.snapshot.snapshot_manager import SnapshotManager


def test_research_api_rejects_missing_as_of_and_snapshot_id():
    api = ResearchDataAPI()

    with pytest.raises(ValueError, match="requires an explicit as_of datetime or snapshot_id"):
        api.get_prices(["600519.SH"], "2022-01-01", "2022-01-10")

    with pytest.raises(ValueError, match="requires an explicit as_of datetime or snapshot_id"):
        api.get_fundamentals("600519.SH", effective_date="2021-12-31")

    with pytest.raises(ValueError, match="requires an explicit as_of datetime or snapshot_id"):
        api.get_metric("600519.SH", "pe_ttm", "2021-12-31")


def test_snapshot_manager_rejects_missing_as_of_and_snapshot_id():
    mgr = SnapshotManager()

    with pytest.raises(ValueError, match="Either as_of datetime or snapshot_id must be provided"):
        mgr.query_market_data("600519.SH", "2022-01-01", "2022-01-10")
