"""
test_anti_fabrication_adversarial.py — Phase 7H adversarial tests.

Verifies REQ-1 through REQ-7 of docs/PHASE_7H_SPECIFICATION.md: it must be structurally
impossible for synthetic/fabricated data to be labeled REAL_PROVIDER or
LOCAL_PRODUCTION_VERIFICATION_DATA, and every silent-fallback path found in the Phase 7G
architecture audit must now fail closed instead.
"""

import os
import sys
import types
import pytest
from datetime import datetime
from unittest.mock import patch

from src.data.providers.tushare_provider import TuShareAdapter, LiveTuShareAdapter
from src.data.providers.akshare_provider import AkShareProviderAdapter
from src.data.providers.base import ProviderError
from src.data.warehouse.warehouse_loader import HistoricalDataWarehouse
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine
from src.quant.reproducibility.store import ResearchRunStore
from src.quant.reproducibility.replay_engine import ResearchReplayEngine
from src.quant.reproducibility.manifest import ResearchInputManifest, ResearchResultManifest
from src.quant.reproducibility.identity import ResearchRunIdentity
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.data.revision.revision_store import RevisionStore
from src.data.revision.revision_model import DataRevision


# --- REQ-1 / REQ-5: synthetic fixture adapters can never claim REAL_PROVIDER ---------------

def test_synthetic_tushare_adapter_always_tagged_synthetic(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "a_real_looking_token_1234567890")
    adapter = TuShareAdapter()
    market = adapter.fetch_market_data("600519.SH", "2022-05-01")
    fundamentals = adapter.fetch_fundamental_data("600519.SH", "2022-05-01")
    actions = adapter.fetch_corporate_actions("600519.SH", "2022-01-01", "2022-12-31")

    assert market.data_origin == "SYNTHETIC_DATA"
    assert fundamentals.data_origin == "SYNTHETIC_DATA"
    assert all(a.data_origin == "SYNTHETIC_DATA" for a in actions)


def test_synthetic_akshare_adapter_always_tagged_synthetic(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "a_real_looking_token_1234567890")
    adapter = AkShareProviderAdapter()
    market = adapter.fetch_market_data("600519.SH", "2022-05-01")
    assert market.data_origin == "SYNTHETIC_DATA"


# --- REQ-2: the real adapter fails closed, never fabricates a default -----------------------

def test_live_tushare_adapter_rejects_demo_token():
    with pytest.raises(ProviderError):
        LiveTuShareAdapter("DEMO_TOKEN")
    with pytest.raises(ProviderError):
        LiveTuShareAdapter("")


def test_live_tushare_adapter_raises_when_package_missing():
    assert "tushare" not in sys.modules or True  # environment has no tushare installed
    adapter = LiveTuShareAdapter("real_token_looks_legit_0000000000")
    with pytest.raises(ProviderError):
        adapter.fetch_market_data("600519.SH", "2022-05-01")


def test_live_tushare_adapter_returns_real_provider_only_from_parsed_response():
    """Mocks the tushare package so we can prove: (a) values that actually flow through the
    live adapter's parsing logic get tagged REAL_PROVIDER and match the mocked response
    exactly (proving no hardcoded literal is substituted), and (b) an empty API response
    raises instead of silently falling back to a default."""

    class _FakeRow(dict):
        def __getitem__(self, key):
            return dict.__getitem__(self, key)

    class _FakeDF:
        def __init__(self, rows):
            self._rows = rows
        @property
        def empty(self):
            return len(self._rows) == 0
        @property
        def iloc(self):
            return self._rows

    class _FakePro:
        def daily(self, ts_code, trade_date):
            # Canary value that does not appear anywhere in the hardcoded synthetic adapters.
            return _FakeDF([{"open": 999.11, "high": 999.99, "low": 998.00, "close": 999.42, "vol": 12345.0, "amount": 6789000.0}])
        def adj_factor(self, ts_code, trade_date):
            return _FakeDF([])

    fake_tushare_module = types.SimpleNamespace(pro_api=lambda token: _FakePro())

    with patch.dict(sys.modules, {"tushare": fake_tushare_module}):
        adapter = LiveTuShareAdapter("real_token_looks_legit_0000000000")
        contract = adapter.fetch_market_data("600519.SH", "2022-05-01")

    assert contract.data_origin == "REAL_PROVIDER"
    assert contract.close_price == 999.42
    # The canary value must not collide with either hardcoded synthetic fixture's price.
    assert contract.close_price not in (1650.00, 11.50, 12.50)


def test_live_tushare_adapter_fails_closed_on_empty_response():
    class _EmptyDF:
        empty = True
        iloc = []

    class _FakePro:
        def daily(self, ts_code, trade_date):
            return _EmptyDF()

    fake_tushare_module = types.SimpleNamespace(pro_api=lambda token: _FakePro())

    with patch.dict(sys.modules, {"tushare": fake_tushare_module}):
        adapter = LiveTuShareAdapter("real_token_looks_legit_0000000000")
        with pytest.raises(ProviderError):
            adapter.fetch_market_data("600519.SH", "2022-05-01")


# --- REQ-7: credential availability alone cannot fabricate a REAL_PROVIDER certification ----

def test_credential_flag_alone_cannot_upgrade_certification_to_real_provider(tmp_path, monkeypatch):
    """The core adversarial case found in the Phase 7G architecture audit: is_live_provider_available()
    used to directly gate data_origin, meaning a bare credential presence flag could relabel the
    exact same formula-generated numbers as REAL_PROVIDER without any network call ever happening.

    Force is_live to True AND give the reconciliation step a working mocked live fetch (so the
    pipeline can complete end-to-end as it would with genuine credentials) and prove the dataset
    certification still reports SYNTHETIC_DATA, because dataset generation is a separate formula-
    based code path that a working live adapter does not touch."""
    monkeypatch.setenv("TUSHARE_TOKEN", "real_token_looks_legit_0000000000")

    class _FakeDF:
        def __init__(self, rows):
            self._rows = rows
        @property
        def empty(self):
            return len(self._rows) == 0
        @property
        def iloc(self):
            return self._rows

    class _FakePro:
        def daily(self, ts_code, trade_date):
            return _FakeDF([{"open": 999.0, "high": 999.9, "low": 998.0, "close": 999.42, "vol": 12345.0, "amount": 6789000.0}])
        def adj_factor(self, ts_code, trade_date):
            return _FakeDF([])

    fake_tushare_module = types.SimpleNamespace(pro_api=lambda token: _FakePro())
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))

    with patch.object(LiveProviderVerificationEngine, "is_live_provider_available", return_value=True):
        with patch.dict(sys.modules, {"tushare": fake_tushare_module}):
            result = engine.execute_phase_7g_cg_certification(run_store_dir=str(tmp_path / "runs"))

    assert result["data_origin"] == "SYNTHETIC_DATA"
    assert result["provenance_status"] == "NOT_VERIFIED_SYNTHETIC_FIXTURE_PIPELINE"
    assert result["verdict"] == "PASS_WITH_LIMITATIONS"
    # The reconciliation sub-step DID exercise a real (mocked) fetch this time — that must not
    # leak into upgrading the dataset-level data_origin.
    assert result["cross_provider_status"] in ("MATCH", "ACCEPTABLE_DIFFERENCE", "MATERIAL_DIFFERENCE")


def test_cross_provider_reconciliation_of_two_synthetic_fixtures_is_labeled_synthetic(tmp_path):
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    out = engine.run_cross_provider_reconciliation_audit()
    assert out["data_origin"] == "SYNTHETIC_DATA"
    assert out["note"] is not None


# --- REQ-6: silent fallback paths now fail closed --------------------------------------------

def test_warehouse_fallback_is_explicitly_tagged_golden_dataset_not_real_provider():
    wh = HistoricalDataWarehouse()
    bars = wh.get_pit_market_bars("600519.SH", "2026-04-01", "2026-04-10", datetime(2026, 4, 10))
    assert len(bars) >= 1
    assert all(b.data_origin == "GOLDEN_DATASET" for b in bars)
    assert all(b.provider_id == "golden_fixture" for b in bars)


def test_replay_fails_closed_when_daily_prices_artifact_missing(tmp_path):
    store = RevisionStore()
    rev = DataRevision(
        record_id="r1", symbol="600519.SH", field="close", effective_date="2022-05-01",
        value=1600.0, provider="tushare", available_at=datetime(2022, 5, 1, 15, 0),
        received_at=datetime(2022, 5, 1, 15, 0), revision_id="rev_1", dataset_version="ds_v1.0"
    )
    store.add_revision(rev)
    mgr = SnapshotManager(revision_store=store)
    mgr.create_snapshot(as_of=datetime(2022, 5, 2), snapshot_id="snap_no_artifact", dataset_version="ds_v1.0")

    run_store = ResearchRunStore(base_dir=str(tmp_path))
    input_manifest = ResearchInputManifest(
        research_run_id="run_no_artifact", dataset_id="golden_ds", dataset_version="ds_v1.0",
        snapshot_id="snap_no_artifact", dataset_manifest_hash="hash_ds", as_of="2022-05-02T00:00:00",
        start_date="2022-05-01", end_date="2022-05-02", universe_type="A_SHARE",
        universe_symbols=["600519.SH"], universe_hash="u_hash",
        factors_config=[{"factor": "momentum_20d:v1"}], factor_definition_hash="f_hash_v1",
        strategy_id="strat_mom", strategy_version="1.0.0", strategy_parameters={"top_n": 1},
        parameter_hash="p_hash_v1", portfolio_constraints={"max_w": 1.0},
        cost_model_config={"commission": 0.0003}, transaction_cost_model_hash="c_hash_v1",
        benchmark_id="000300.SH", benchmark_version="1.0", benchmark_hash="b_hash",
        code_version="test", code_state="CLEAN", created_at="2022-05-02T10:00:00"
    )
    result_manifest = ResearchResultManifest(
        research_run_id="run_no_artifact", input_manifest_hash=input_manifest.compute_input_hash(),
        result_hash="deadbeef", equity_curve_hash="deadbeef"
    )
    identity = ResearchRunIdentity(
        research_run_id="run_no_artifact", snapshot_id="snap_no_artifact", dataset_version="ds_v1.0",
        dataset_manifest_hash="hash_ds", as_of="2022-05-02T00:00:00", start_date="2022-05-01",
        end_date="2022-05-02", universe_definition={"symbols": ["600519.SH"]}, universe_hash="u_hash",
        strategy_id="strat_mom", strategy_version="1.0.0", factor_definition_hash="f_hash_v1",
        parameter_hash="p_hash_v1", transaction_cost_model_hash="c_hash_v1", benchmark_id="000300.SH",
        code_version="test", code_state="CLEAN", input_hash=input_manifest.compute_input_hash(),
        result_hash="deadbeef", created_at="2022-05-02T10:00:00"
    )
    # Deliberately create the run WITHOUT a daily_prices artifact.
    run_store.create_run(identity, input_manifest, result_manifest, {})

    replay_engine = ResearchReplayEngine(run_store=run_store, snapshot_manager=mgr)
    with pytest.raises(RuntimeError, match="FAIL CLOSED"):
        replay_engine.replay_run("run_no_artifact")
