"""
test_pit_adversarial_attacks.py — Adversarial Attack Tests attempting to bypass PIT / Snapshot / Revision architecture.
"""

import pytest
from datetime import datetime
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.quant.data.research_api import ResearchDataAPI
from src.quant.factors.value import ValuationFactorAdapter
from src.quant.factors.base import FactorStatus
from src.data.contracts.fundamental_data import MetricProvenance
from src.data.domain.security_master import SecurityMasterContract, SecurityMasterRegistry


def test_attack_1_un_gated_query_without_as_of_fails():
    """Attack 1: Attempt to query ResearchDataAPI without passing as_of or snapshot_id."""
    api = ResearchDataAPI()
    with pytest.raises(ValueError, match="requires an explicit as_of datetime or snapshot_id"):
        api.get_prices(["600519.SH"], "2022-01-01", "2022-01-10")


def test_attack_2_current_only_metric_injected_into_factor_fails():
    """Attack 2: Attempt to compute historical factor using CURRENT_ONLY metric provenance."""
    adapter = ValuationFactorAdapter("pe_ttm")
    val = adapter.compute_from_fundamental(
        symbol="600519.SH", val=99.0, provenance=MetricProvenance.CURRENT_ONLY,
        effective_date="2022-03-31", as_of=datetime(2022, 5, 1)
    )
    assert val.status == FactorStatus.NOT_APPLICABLE
    assert val.raw_value is None


def test_attack_3_future_backfilled_revision_cannot_corrupt_old_snapshot():
    """Attack 3: Inject a future backfilled revision into store and verify old snapshot is immune."""
    store = RevisionStore()
    rev_t1 = DataRevision(
        record_id="r1", symbol="600519.SH", field="close", effective_date="2022-05-01",
        value=1600.0, provider="tushare", available_at=datetime(2022, 5, 1, 15, 0),
        received_at=datetime(2022, 5, 1, 15, 0), revision_id="rev_1", dataset_version="ds_v1"
    )
    store.add_revision(rev_t1)

    mgr = SnapshotManager(revision_store=store)
    snap = mgr.create_snapshot(as_of=datetime(2022, 5, 2), snapshot_id="snap_frozen")

    # Adversarial injection at T2
    rev_t2 = DataRevision(
        record_id="r2", symbol="600519.SH", field="close", effective_date="2022-05-01",
        value=9999.0, provider="tushare", available_at=datetime(2022, 5, 1, 15, 0),
        received_at=datetime(2022, 6, 1, 15, 0), revision_id="rev_hacked", dataset_version="ds_v2"
    )
    store.add_revision(rev_t2)

    res = mgr.query_market_data("600519.SH", "2022-05-01", "2022-05-01", snapshot_id=snap.snapshot_id)
    assert len(res) == 1
    assert res[0].value == 1600.0  # IMMUNE to hacked revision!
    assert res[0].value != 9999.0


def test_attack_4_missing_pit_data_returns_unavailable_not_zero():
    """Attack 4: Missing historical PIT data must return UNAVAILABLE, never 0 or fillna(0)."""
    store = RevisionStore()
    mgr = SnapshotManager(revision_store=store)
    api = ResearchDataAPI(snapshot_manager=mgr, revision_store=store)

    val = api.get_metric("000001.SZ", "roe", "2022-03-31", as_of=datetime(2022, 4, 1))
    assert val == "UNAVAILABLE"
    assert val != 0
    assert val != 0.0


def test_attack_5_delisted_stock_survives_historical_universe_query():
    """Attack 5: Delisted stock cannot be silently wiped from historical universe."""
    reg = SecurityMasterRegistry()
    reg.register(SecurityMasterContract(
        symbol="600000.SH", exchange="SSE", display_name="浦发银行",
        security_type="STOCK", list_date="1999-11-10", delist_date="2025-01-01",
        status="DELISTED", industry_sw_l1="银行", industry_sw_l2="股份制银行"
    ))

    u_2020 = reg.get_historical_universe("2020-01-01")
    assert "600000.SH" in u_2020  # MUST exist in 2020 universe despite delisting in 2025!
