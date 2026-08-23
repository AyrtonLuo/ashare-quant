"""
test_integrity_gate_bypass_adversarial.py — Phase 7J adversarial tests (Directive 007J §6),
updated for Phase 8A's mandatory factor_definitions (CEO directive 008A-IMPLEMENT §3: fixture
setup/input updated to supply a valid factor configuration; no assertion weakened, no test
deleted, no expected result loosened).

Not "does the correct path work" — "is every incorrect path rejected." Each of the 20
scenarios enumerated in the directive gets its own test proving FAIL CLOSED.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.corporate_action import CorporateActionContract
from src.data.storage.parquet_adapter import ParquetStorageAdapter
from src.data.domain.persistent_manifest import PersistentDatasetManifestManager, PersistentDatasetManifestStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.data.domain.security_master import SecurityMasterRegistry, SecurityMasterContract
from src.data.revision.corporate_action_store import CorporateActionStore
from src.data.security.secret_audit import SecurityAuditManager
from src.quant.reproducibility.store import ResearchRunStore
from src.quant.reproducibility.certified_replay_engine import CertifiedReplayEngine
from src.quant.reproducibility.identity import get_code_version
from src.quant.factors.registry import FactorSpec
from src.quant.factors.multi_factor import FactorWeightConfig, FactorDirection
from src.quant.research.integrity_gate import CertifiedResearchRequest, CertifiedResearchRunExecutor

SYMBOL = "600519.SH"
DATES = ["2026-08-01", "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"]
PRICES = [100.0, 100.0, 101.0, 101.0, 102.0]
AS_OF = datetime(2026, 8, 10)

MOMENTUM_ONLY = [FactorSpec("momentum_20d:v1", {"window_days": 3})]
MOMENTUM_ONLY_SIGNAL = [FactorWeightConfig("momentum_20d:v1", 1.0, FactorDirection.POSITIVE)]


def _persist_dataset(tmp_path, dataset_id="ds_test", dataset_version="v1", prices=None):
    prices = prices or PRICES
    adapter = ParquetStorageAdapter(base_dir=str(tmp_path))
    contracts = [
        MarketDataContract(
            symbol=SYMBOL, timestamp=datetime(2026, 8, 1 + i), trading_date=d,
            open_price=p, high_price=p + 1, low_price=p - 1, close_price=p, volume=1000.0,
            amount=100000.0, adj_factor=1.0, unadjusted_close=p, trading_status="NORMAL",
            quality_status="VALID", data_origin="GOLDEN_DATASET",
        )
        for i, (d, p) in enumerate(zip(DATES, prices))
    ]
    adapter.save_market_data(dataset_id, contracts)
    directory = tmp_path / dataset_id
    manifest_store = PersistentDatasetManifestStore()
    manifest = PersistentDatasetManifestManager.build_manifest(
        dataset_id, dataset_version, directory, created_at="2026-08-01T00:00:00"
    )
    manifest_store.certify(manifest)
    return directory, manifest_store


@pytest.fixture
def setup(tmp_path):
    directory, manifest_store = _persist_dataset(tmp_path)

    snapshot_manager = SnapshotManager()
    snapshot_manager.create_snapshot(as_of=AS_OF, dataset_version="v1", snapshot_id="snap_1")

    security_master = SecurityMasterRegistry()
    security_master.register(SecurityMasterContract(
        symbol=SYMBOL, exchange="SSE", display_name="x", security_type="STOCK",
        list_date="2000-01-01", delist_date=None, status="ACTIVE",
        industry_sw_l1="x", industry_sw_l2="x",
    ))

    corporate_action_store = CorporateActionStore()
    run_store = ResearchRunStore(base_dir=str(tmp_path / "runs"))

    return {
        "tmp_path": tmp_path,
        "directory": directory,
        "manifest_store": manifest_store,
        "snapshot_manager": snapshot_manager,
        "security_master": security_master,
        "corporate_action_store": corporate_action_store,
        "run_store": run_store,
    }


def _make_request(setup, run_id="run_1", **overrides):
    base = dict(
        research_run_id=run_id,
        dataset_id="ds_test", dataset_version="v1",
        dataset_directory=str(setup["directory"]), persistent_manifest_store=setup["manifest_store"],
        snapshot_id="snap_1", snapshot_manager=setup["snapshot_manager"], as_of=AS_OF,
        universe_symbols=[SYMBOL], security_master=setup["security_master"],
        corporate_action_store=setup["corporate_action_store"],
        raw_price_series={SYMBOL: (DATES, PRICES)},
        provider_data_origin={SYMBOL: "GOLDEN_DATASET"},
        factor_definitions=MOMENTUM_ONLY,
        fundamental_data={},
        signal_config=MOMENTUM_ONLY_SIGNAL,
        # This file's fixture is single-symbol (its focus is dataset/snapshot/PIT/corp-action/
        # cost-model/replay concerns, not cross-sectional sampling — that gets its own dedicated
        # tests in test_factor_engine_adversarial.py), so the sample-size floor is relaxed here.
        min_cross_sectional_samples=1,
        parameters={"top_n": 1},
        cost_model_config={"commission_rate": 0.0003}, strategy_id="strat_test", strategy_version="1.0.0",
        benchmark_id="000300.SH", benchmark_version="1.0", run_store=setup["run_store"],
    )
    base.update(overrides)
    return CertifiedResearchRequest(**base)


# --- Baseline: the correct path actually works (sanity check the adversarial tests aren't vacuous)

def test_baseline_certified_path_succeeds(setup):
    result, identity = CertifiedResearchRunExecutor.execute(_make_request(setup))
    assert identity.research_run_id == "run_1"
    assert setup["run_store"].get_run("run_1") is not None


def test_baseline_certified_replay_succeeds_when_untampered(setup):
    """Sanity check that CertifiedReplayEngine isn't simply failing everything: an untampered
    run must replay REPRODUCIBLE, not raise."""
    CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_replay_ok"))
    replay_engine = CertifiedReplayEngine(
        setup["run_store"], setup["snapshot_manager"], setup["manifest_store"],
        setup["corporate_action_store"], setup["security_master"], {},
    )
    report = replay_engine.replay("run_replay_ok")
    assert report.status.value == "REPRODUCIBLE"


# --- 1. Backtest without DatasetLock (no certified manifest for the requested version) -------

def test_1_missing_dataset_lock_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, dataset_version="v_never_certified"))


# --- 2. Backtest with missing snapshot ---------------------------------------------------------

def test_2_missing_snapshot_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, snapshot_id="snap_never_created"))


# --- 3. Backtest with mismatched dataset/snapshot ----------------------------------------------

def test_3_mismatched_dataset_snapshot_fails(setup):
    # snapshot 'snap_1' is locked to dataset_version 'v1'; request a different declared version.
    setup["snapshot_manager"].create_snapshot(as_of=AS_OF, dataset_version="v2", snapshot_id="snap_v2")
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(
            _make_request(setup, snapshot_id="snap_v2", dataset_version="v1")
        )


# --- 4. Backtest with modified Parquet bytes ----------------------------------------------------

def test_4_modified_parquet_bytes_fails(setup):
    file_path = setup["directory"] / "600519_SH.parquet"
    df = pd.read_parquet(file_path)
    df.loc[0, "close_price"] = 99999.0
    df.to_parquet(file_path, index=False, engine="pyarrow")

    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup))


# --- 5. Backtest with modified manifest (simulated: re-certify different content under a new
#        version pointed at by a forged manifest_store entry is rejected; direct entry mutation
#        is impossible since the store only exposes certify()/get()) ----------------------------

def test_5_recertifying_different_content_under_same_version_fails(setup):
    file_path = setup["directory"] / "600519_SH.parquet"
    df = pd.read_parquet(file_path)
    df.loc[0, "close_price"] = 12345.0
    df.to_parquet(file_path, index=False, engine="pyarrow")

    new_manifest = PersistentDatasetManifestManager.build_manifest(
        "ds_test", "v1", setup["directory"], created_at="2026-08-01T00:00:00"
    )
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        setup["manifest_store"].certify(new_manifest)


# --- 6. Backtest bypassing PIT (requested as_of doesn't match the locked snapshot) --------------

def test_6_pit_as_of_mismatch_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, as_of=datetime(2026, 9, 1)))


# --- 7. Backtest bypassing corporate-action adjustment ------------------------------------------

def test_7_cannot_bypass_corporate_action_step(setup):
    """There is no parameter on CertifiedResearchRequest to skip adjustment — every symbol is
    routed through CorporateActionAdjuster unconditionally. Prove it by registering a real split
    and checking the certified run's stored artifact reflects the adjusted (not raw) series."""
    split = CorporateActionContract(
        symbol=SYMBOL, ex_date="2026-08-04", action_type="STOCK_SPLIT",
        cash_amount_per_share=0.0, bonus_ratio=0.0, split_ratio=2.0,
        announcement_date="2026-07-20",
        available_at=datetime(2026, 7, 20), received_at=datetime(2026, 7, 20),
        quality_status="VALID",
    )
    setup["corporate_action_store"].add_action(split)

    raw = [100.0, 100.0, 50.0, 50.0, 50.0]
    _, identity = CertifiedResearchRunExecutor.execute(
        _make_request(setup, run_id="run_split", raw_price_series={SYMBOL: (DATES, raw)})
    )
    stored = setup["run_store"].get_run("run_split")
    adjusted = stored["artifacts"]["daily_prices"][SYMBOL]
    assert adjusted == [50.0, 50.0, 50.0, 50.0, 50.0], "adjustment must have been applied, not skipped"
    assert stored["artifacts"]["corporate_actions_applied"][SYMBOL] != []


# --- 8. Backtest using unavailable required corporate-action data (invalid dividend) -----------

def test_8_invalid_corporate_action_data_fails_closed(setup):
    bad_dividend = CorporateActionContract(
        symbol=SYMBOL, ex_date="2026-08-04", action_type="CASH_DIVIDEND",
        cash_amount_per_share=999.0, bonus_ratio=0.0, split_ratio=1.0,  # dividend >= price
        announcement_date="2026-07-20",
        available_at=datetime(2026, 7, 20), received_at=datetime(2026, 7, 20),
        quality_status="VALID",
    )
    setup["corporate_action_store"].add_action(bad_dividend)
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_bad_div"))


# --- 9. Backtest using historical universe inconsistent with as_of ------------------------------

def test_9_universe_inconsistent_with_as_of_fails(setup):
    setup["security_master"].register(SecurityMasterContract(
        symbol="000001.SZ", exchange="SZSE", display_name="y", security_type="STOCK",
        list_date="2000-01-01", delist_date="2026-01-01", status="DELISTED",
        industry_sw_l1="x", industry_sw_l2="x",
    ))
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(
            setup, run_id="run_delisted",
            universe_symbols=[SYMBOL, "000001.SZ"],
            raw_price_series={SYMBOL: (DATES, PRICES), "000001.SZ": (DATES, PRICES)},
            provider_data_origin={SYMBOL: "GOLDEN_DATASET", "000001.SZ": "GOLDEN_DATASET"},
        ))


# --- 10-12. Mismatched factor / parameter / cost-model — empty binding fails closed -------------

def test_10_empty_factor_definitions_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, factor_definitions=[]))


def test_11_empty_parameters_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, parameters={}))


def test_12_empty_cost_model_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, cost_model_config={}))


def test_12b_unrecognized_cost_model_keys_fail_closed(setup):
    """A cost_model_config with fields TransactionCostModel doesn't recognize must fail
    closed, not silently be hashed-and-ignored (the exact bug found in Phase 7J's own second
    audit: the config was previously bound into the hash but never applied to the engine)."""
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(
            _make_request(setup, cost_model_config={"totally_made_up_field": 0.01})
        )


def test_12c_cost_model_config_actually_drives_the_engine(setup):
    """Prove the binding is real: two runs differing ONLY in commission_rate must produce
    different total_return, not identical results from an ignored config."""
    result_low, _ = CertifiedResearchRunExecutor.execute(
        _make_request(setup, run_id="run_cost_low", cost_model_config={"commission_rate": 0.0001})
    )
    result_high, _ = CertifiedResearchRunExecutor.execute(
        _make_request(setup, run_id="run_cost_high", cost_model_config={"commission_rate": 0.05})
    )
    assert result_low.total_return != result_high.total_return


# --- 13. Mismatched / missing provider provenance ------------------------------------------------

def test_13_unrecognized_provider_provenance_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(
            _make_request(setup, provider_data_origin={SYMBOL: "TOTALLY_MADE_UP_ORIGIN"})
        )


def test_13b_missing_provider_provenance_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, provider_data_origin={}))


# --- 14. Replay against modified dataset ----------------------------------------------------------

def test_14_replay_against_modified_dataset_fails(setup):
    CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_replay_1"))

    file_path = setup["directory"] / "600519_SH.parquet"
    df = pd.read_parquet(file_path)
    df.loc[0, "close_price"] = 77777.0
    df.to_parquet(file_path, index=False, engine="pyarrow")

    replay_engine = CertifiedReplayEngine(
        setup["run_store"], setup["snapshot_manager"], setup["manifest_store"],
        setup["corporate_action_store"], setup["security_master"], {},
    )
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        replay_engine.replay("run_replay_1")


# --- 15. Replay against modified/missing snapshot --------------------------------------------------

def test_15_replay_against_missing_snapshot_fails(setup):
    fresh_snapshot_manager = SnapshotManager()  # 'snap_1' never registered here
    CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_replay_2"))

    replay_engine = CertifiedReplayEngine(
        setup["run_store"], fresh_snapshot_manager, setup["manifest_store"],
        setup["corporate_action_store"], setup["security_master"], {},
    )
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        replay_engine.replay("run_replay_2")


# --- 16. Replay against modified corporate-action data ----------------------------------------------

def test_16_replay_against_changed_corporate_action_data_fails(setup):
    CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_replay_3"))

    # A corporate action is added to the store AFTER certification — replay must detect that the
    # PIT-visible action set for this run's as_of has changed since the run was certified.
    late_added_split = CorporateActionContract(
        symbol=SYMBOL, ex_date="2026-08-04", action_type="STOCK_SPLIT",
        cash_amount_per_share=0.0, bonus_ratio=0.0, split_ratio=2.0,
        announcement_date="2026-07-20",
        available_at=datetime(2026, 7, 20), received_at=datetime(2026, 7, 20),
        quality_status="VALID",
    )
    setup["corporate_action_store"].add_action(late_added_split)

    replay_engine = CertifiedReplayEngine(
        setup["run_store"], setup["snapshot_manager"], setup["manifest_store"],
        setup["corporate_action_store"], setup["security_master"], {},
    )
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        replay_engine.replay("run_replay_3")


# --- 17. Attempt to mutate an immutable dataset (re-certify different content) ---------------------

def test_17_mutating_certified_dataset_fails(setup):
    file_path = setup["directory"] / "600519_SH.parquet"
    df = pd.read_parquet(file_path)
    df.loc[0, "close_price"] = 55555.0
    df.to_parquet(file_path, index=False, engine="pyarrow")

    mutated_manifest = PersistentDatasetManifestManager.build_manifest(
        "ds_test", "v1", setup["directory"], created_at="2026-08-01T00:00:00"
    )
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        setup["manifest_store"].certify(mutated_manifest)


# --- 18. Attempt to overwrite an immutable research run ---------------------------------------------

def test_18_overwriting_immutable_research_run_fails(setup):
    CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_immutable"))
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_immutable"))


# --- 19. Dirty working-tree handling must remain correct ---------------------------------------------

def test_19_code_version_reflects_real_git_state(setup):
    code_version, code_state = get_code_version()
    assert code_version != "UNAVAILABLE"
    assert code_state in ("CLEAN", "DIRTY")

    _, identity = CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_dirty_check"))
    assert identity.code_version == code_version
    assert identity.code_state == code_state


# --- 20. Secret audit must reject actual secret leakage -----------------------------------------------

def test_20_secret_audit_rejects_actual_leak(tmp_path):
    (tmp_path / "leaked.log").write_text("token=sk_live_realsecret1234567890")
    res = SecurityAuditManager.audit_directory_for_secrets(str(tmp_path))
    assert res["status"] == "FAILED_LEAK_DETECTED"
    assert res["security_certification"] == "FAIL_SECRET_LEAK"


# --- RIGHTS_OFFERING (配股) — RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md end-to-end ----

def test_rights_offering_consumed_by_certified_run(setup):
    """Same proof shape as test_7_cannot_bypass_corporate_action_step above, for the newly
    implemented RIGHTS_OFFERING type: a registered rights offering is routed through
    CorporateActionAdjuster unconditionally by the certified path."""
    rights = CorporateActionContract(
        symbol=SYMBOL, ex_date="2026-08-04", action_type="RIGHTS_OFFERING",
        cash_amount_per_share=0.0, bonus_ratio=0.0, split_ratio=1.0,
        announcement_date="2026-07-20",
        available_at=datetime(2026, 7, 20), received_at=datetime(2026, 7, 20),
        quality_status="VALID", rights_ratio=0.3, subscription_price=6.0,
    )
    setup["corporate_action_store"].add_action(rights)

    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    _, identity = CertifiedResearchRunExecutor.execute(
        _make_request(setup, run_id="run_rights", raw_price_series={SYMBOL: (DATES, raw)})
    )
    stored = setup["run_store"].get_run("run_rights")
    expected_factor = (90.0 + 0.3 * 6.0) / (90.0 * 1.3)
    adjusted = stored["artifacts"]["daily_prices"][SYMBOL]
    assert adjusted[0] == pytest.approx(round(raw[0] * expected_factor, 6))
    assert adjusted != raw, "adjustment must have been applied, not skipped"
    assert stored["artifacts"]["corporate_actions_applied"][SYMBOL] != []


def test_rights_offering_replay_reproducible(setup):
    """RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md §7: CertifiedReplayEngine needs zero
    code changes since it already calls the same CorporateActionAdjuster.adjust() the certified
    path uses — proven behaviorally here, not just by code-path inspection."""
    rights = CorporateActionContract(
        symbol=SYMBOL, ex_date="2026-08-04", action_type="RIGHTS_OFFERING",
        cash_amount_per_share=0.0, bonus_ratio=0.0, split_ratio=1.0,
        announcement_date="2026-07-20",
        available_at=datetime(2026, 7, 20), received_at=datetime(2026, 7, 20),
        quality_status="VALID", rights_ratio=0.3, subscription_price=6.0,
    )
    setup["corporate_action_store"].add_action(rights)

    raw = [100.0, 100.0, 90.0, 90.0, 90.0]
    CertifiedResearchRunExecutor.execute(
        _make_request(setup, run_id="run_rights_replay", raw_price_series={SYMBOL: (DATES, raw)})
    )
    replay_engine = CertifiedReplayEngine(
        setup["run_store"], setup["snapshot_manager"], setup["manifest_store"],
        setup["corporate_action_store"], setup["security_master"], {},
    )
    report = replay_engine.replay("run_rights_replay")
    assert report.status.value == "REPRODUCIBLE"
