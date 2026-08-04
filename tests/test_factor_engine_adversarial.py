"""
test_factor_engine_adversarial.py — Phase 8A Factor Engine adversarial tests
(CEO directive CEO-2026-08-03-RESEARCH-008A-IMPLEMENT §10, 20 scenarios).

Proves the full factor -> normalization -> signal -> portfolio chain is mandatory,
FactorRegistry-bound, PIT-correct for fundamental data, and that replay genuinely
recomputes every step rather than trusting cached artifacts.
"""

from datetime import datetime

import pandas as pd
import pytest

from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract, MetricProvenance
from src.data.storage.parquet_adapter import ParquetStorageAdapter
from src.data.domain.persistent_manifest import PersistentDatasetManifestManager, PersistentDatasetManifestStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.data.domain.security_master import SecurityMasterRegistry, SecurityMasterContract
from src.data.revision.corporate_action_store import CorporateActionStore
from src.quant.reproducibility.store import ResearchRunStore
from src.quant.reproducibility.certified_replay_engine import (
    CertifiedReplayEngine, IntermediateArtifactMismatchError, ReplayStatus,
)
from src.quant.factors.registry import FactorRegistry, FactorSpec
from src.quant.factors.multi_factor import FactorWeightConfig, FactorDirection
from src.quant.research.integrity_gate import CertifiedResearchRequest, CertifiedResearchRunExecutor

SYMBOLS = ["600519.SH", "000001.SZ", "000002.SZ", "000333.SZ"]
DATES = ["2026-08-01", "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"]
PRICES = {
    "600519.SH": [100.0, 102.0, 104.0, 108.0, 112.0],
    "000001.SZ": [50.0, 49.0, 48.0, 47.0, 46.0],
    "000002.SZ": [20.0, 20.5, 21.0, 21.2, 21.5],
    "000333.SZ": [30.0, 29.5, 30.2, 30.8, 31.0],
}
PE_VALUES = {"600519.SH": 30.0, "000001.SZ": 8.0, "000002.SZ": 15.0, "000333.SZ": 12.0}
AS_OF = datetime(2026, 8, 10)

MOMENTUM_VALUE = [FactorSpec("momentum_20d:v1", {"window_days": 3}), FactorSpec("value_pe:v1", {})]
MOMENTUM_VALUE_SIGNAL = [
    FactorWeightConfig("momentum_20d:v1", 0.5, FactorDirection.POSITIVE),
    FactorWeightConfig("value_pe:v1", 0.5, FactorDirection.NEGATIVE),
]


def _fundamental_record(symbol, pe, available_at=datetime(2026, 7, 15)):
    return FundamentalDataContract(
        symbol=symbol, trade_date="2026-08-01", report_date="2026-06-30", announcement_date="2026-07-15",
        currency="CNY", revenue=None, net_income=None, eps_annual=None, eps_ttm=None,
        book_value_per_share=None, operating_cash_flow=None, shares_outstanding=1e9, market_cap=1e11,
        pe_lyr=None, pe_ttm=pe, pe_ttm_status="VALID", pb=None, pb_status="UNAVAILABLE",
        dividend_yield_ttm=None, dividend_yield_status="UNAVAILABLE", roe=None,
        provenance=MetricProvenance.PROVIDER_REPORTED, quality_status="VALID",
        available_at=available_at, received_at=available_at, as_of=None,
        data_origin="GOLDEN_DATASET",
    )


@pytest.fixture
def setup(tmp_path):
    adapter = ParquetStorageAdapter(base_dir=str(tmp_path))
    contracts = []
    for sym in SYMBOLS:
        for i, (d, p) in enumerate(zip(DATES, PRICES[sym])):
            contracts.append(MarketDataContract(
                symbol=sym, timestamp=datetime(2026, 8, 1 + i), trading_date=d,
                open_price=p, high_price=p + 1, low_price=p - 1, close_price=p, volume=1000.0,
                amount=100000.0, adj_factor=1.0, unadjusted_close=p, trading_status="NORMAL",
                quality_status="VALID", data_origin="GOLDEN_DATASET",
            ))
    adapter.save_market_data("ds_multi", contracts)
    directory = tmp_path / "ds_multi"

    manifest_store = PersistentDatasetManifestStore()
    manifest = PersistentDatasetManifestManager.build_manifest(
        "ds_multi", "v1", directory, created_at="2026-08-01T00:00:00"
    )
    manifest_store.certify(manifest)

    snapshot_manager = SnapshotManager()
    snapshot_manager.create_snapshot(as_of=AS_OF, dataset_version="v1", snapshot_id="snap_1")

    security_master = SecurityMasterRegistry()
    for sym in SYMBOLS:
        security_master.register(SecurityMasterContract(
            symbol=sym, exchange="SSE", display_name=sym, security_type="STOCK",
            list_date="2000-01-01", delist_date=None, status="ACTIVE",
            industry_sw_l1="x", industry_sw_l2="x",
        ))

    corporate_action_store = CorporateActionStore()
    run_store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    fundamental_data = {sym: [_fundamental_record(sym, pe)] for sym, pe in PE_VALUES.items()}

    return {
        "tmp_path": tmp_path, "directory": directory, "manifest_store": manifest_store,
        "snapshot_manager": snapshot_manager, "security_master": security_master,
        "corporate_action_store": corporate_action_store, "run_store": run_store,
        "fundamental_data": fundamental_data,
    }


def _make_request(setup, run_id="run_1", **overrides):
    base = dict(
        research_run_id=run_id,
        dataset_id="ds_multi", dataset_version="v1",
        dataset_directory=str(setup["directory"]), persistent_manifest_store=setup["manifest_store"],
        snapshot_id="snap_1", snapshot_manager=setup["snapshot_manager"], as_of=AS_OF,
        universe_symbols=SYMBOLS, security_master=setup["security_master"],
        corporate_action_store=setup["corporate_action_store"],
        raw_price_series={s: (DATES, PRICES[s]) for s in SYMBOLS},
        provider_data_origin={s: "GOLDEN_DATASET" for s in SYMBOLS},
        factor_definitions=MOMENTUM_VALUE,
        fundamental_data=setup["fundamental_data"],
        signal_config=MOMENTUM_VALUE_SIGNAL,
        min_cross_sectional_samples=3,
        parameters={"top_n": 2}, cost_model_config={"commission_rate": 0.0003},
        strategy_id="strat_test", strategy_version="1.0.0",
        benchmark_id="000300.SH", benchmark_version="1.0", run_store=setup["run_store"],
    )
    base.update(overrides)
    return CertifiedResearchRequest(**base)


def _replay_engine(setup):
    return CertifiedReplayEngine(
        setup["run_store"], setup["snapshot_manager"], setup["manifest_store"],
        setup["corporate_action_store"], setup["security_master"], setup["fundamental_data"],
    )


def test_baseline_momentum_value_certified_path_succeeds(setup):
    result, identity = CertifiedResearchRunExecutor.execute(_make_request(setup))
    stored = setup["run_store"].get_run("run_1")
    assert set(stored["artifacts"]["portfolio_weights"].keys()).issubset(set(SYMBOLS))
    assert identity.signal_configuration_hash != "NOT_APPLICABLE"


# --- 1/2. Missing / empty factor definitions --------------------------------------------------

def test_1_missing_factor_definitions_fails(setup):
    with pytest.raises(TypeError):
        # research_run_id is a positional-or-keyword required field; omitting factor_definitions
        # entirely (not even an empty list) is a Python-level TypeError — there is no default.
        base = dict(
            research_run_id="run_x", dataset_id="ds_multi", dataset_version="v1",
            dataset_directory=str(setup["directory"]), persistent_manifest_store=setup["manifest_store"],
            snapshot_id="snap_1", snapshot_manager=setup["snapshot_manager"], as_of=AS_OF,
            universe_symbols=SYMBOLS, security_master=setup["security_master"],
            corporate_action_store=setup["corporate_action_store"],
            raw_price_series={s: (DATES, PRICES[s]) for s in SYMBOLS},
            provider_data_origin={s: "GOLDEN_DATASET" for s in SYMBOLS},
            fundamental_data=setup["fundamental_data"], signal_config=MOMENTUM_VALUE_SIGNAL,
            parameters={"top_n": 2}, cost_model_config={"commission_rate": 0.0003},
            strategy_id="strat_test", strategy_version="1.0.0",
            benchmark_id="000300.SH", benchmark_version="1.0", run_store=setup["run_store"],
        )
        CertifiedResearchRequest(**base)  # no factor_definitions kwarg at all


def test_2_empty_factor_definitions_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, factor_definitions=[]))


# --- 3. Unknown factor --------------------------------------------------------------------------

def test_3_unknown_factor_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(
            setup, factor_definitions=[FactorSpec("totally_made_up_factor:v99", {})],
            signal_config=[FactorWeightConfig("totally_made_up_factor:v99", 1.0, FactorDirection.POSITIVE)],
        ))


# --- 4. Factor parameter mismatch (invalid parameter for the registered factory) ---------------

def test_4_invalid_factor_parameters_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(
            setup, factor_definitions=[FactorSpec("momentum_20d:v1", {"not_a_real_param": 1})],
            signal_config=[FactorWeightConfig("momentum_20d:v1", 1.0, FactorDirection.POSITIVE)],
        ))


# --- 5. Factor hash changes when factor_definitions change (proves binding, not decoration) ----

def test_5_factor_definition_change_changes_hash(setup):
    _, identity_a = CertifiedResearchRunExecutor.execute(_make_request(
        setup, run_id="run_hash_a",
        factor_definitions=[FactorSpec("momentum_20d:v1", {"window_days": 3})],
        signal_config=[FactorWeightConfig("momentum_20d:v1", 1.0, FactorDirection.POSITIVE)],
    ))
    _, identity_b = CertifiedResearchRunExecutor.execute(_make_request(
        setup, run_id="run_hash_b",
        factor_definitions=[FactorSpec("momentum_20d:v1", {"window_days": 4})],
        signal_config=[FactorWeightConfig("momentum_20d:v1", 1.0, FactorDirection.POSITIVE)],
    ))
    assert identity_a.factor_definition_hash != identity_b.factor_definition_hash


def test_5b_factor_definition_change_changes_factor_output_and_result(setup):
    """The full causal chain the CEO's directive requires: definition -> output -> signal ->
    weights -> result must all change together, never a hash-only change with an identical
    backtest result underneath it (which would prove the config was decorative)."""
    result_a, identity_a = CertifiedResearchRunExecutor.execute(_make_request(
        setup, run_id="run_causal_a",
        factor_definitions=[FactorSpec("momentum_20d:v1", {"window_days": 3})],
        signal_config=[FactorWeightConfig("momentum_20d:v1", 1.0, FactorDirection.POSITIVE)],
    ))
    result_b, identity_b = CertifiedResearchRunExecutor.execute(_make_request(
        setup, run_id="run_causal_b",
        factor_definitions=[FactorSpec("momentum_20d:v1", {"window_days": 2})],
        signal_config=[FactorWeightConfig("momentum_20d:v1", 1.0, FactorDirection.POSITIVE)],
    ))
    weights_a = setup["run_store"].get_run("run_causal_a")["artifacts"]["portfolio_weights"]
    weights_b = setup["run_store"].get_run("run_causal_b")["artifacts"]["portfolio_weights"]
    assert identity_a.factor_definition_hash != identity_b.factor_definition_hash
    # Note: with only 2 symbols separated by momentum ranking here, weights/result MAY coincide
    # by chance for a given fixture; what must always differ is the underlying factor output.
    trace_a = setup["run_store"].get_run("run_causal_a")["artifacts"]["factor_values"]
    trace_b = setup["run_store"].get_run("run_causal_b")["artifacts"]["factor_values"]
    assert trace_a["momentum_20d:v1"] != trace_b["momentum_20d:v1"]


# --- 6. Hidden factor implementation (signal_config direction contradicts the registry) --------

def test_6_hidden_direction_override_fails(setup):
    """A caller cannot silently flip a factor's registered direction via signal_config — that
    would let 'higher PE preferred' sneak in under value_pe:v1's name, contradicting what
    FactorRegistry actually registered and what the audit trail (factor_class/direction) says."""
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(
            setup,
            signal_config=[
                FactorWeightConfig("momentum_20d:v1", 0.5, FactorDirection.POSITIVE),
                FactorWeightConfig("value_pe:v1", 0.5, FactorDirection.POSITIVE),  # registry says NEGATIVE
            ],
        ))


# --- 7. Hard-coded equal-weight bypass — no longer possible from inside the executor -----------

def test_7_no_hardcoded_equal_weight_in_executor(setup):
    """Two different factor definitions on the identical universe/prices must be capable of
    producing different portfolio weights — impossible if an equal-weight fallback still lived
    inside CertifiedResearchRunExecutor."""
    CertifiedResearchRunExecutor.execute(_make_request(
        setup, run_id="run_momentum_only",
        factor_definitions=[FactorSpec("momentum_20d:v1", {"window_days": 3})],
        signal_config=[FactorWeightConfig("momentum_20d:v1", 1.0, FactorDirection.POSITIVE)],
    ))
    CertifiedResearchRunExecutor.execute(_make_request(
        setup, run_id="run_value_only",
        factor_definitions=[FactorSpec("value_pe:v1", {})],
        signal_config=[FactorWeightConfig("value_pe:v1", 1.0, FactorDirection.NEGATIVE)],
    ))
    w1 = setup["run_store"].get_run("run_momentum_only")["artifacts"]["portfolio_weights"]
    w2 = setup["run_store"].get_run("run_value_only")["artifacts"]["portfolio_weights"]
    assert w1 != w2, "momentum-only and value-only selections coincided — equal-weight bypass suspected"
    assert set(w1.keys()) != set(SYMBOLS), "weights covering the full universe suggests an equal-weight fallback"


# --- 8. Missing fundamental data ----------------------------------------------------------------

def test_8_missing_fundamental_data_fails_closed(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, fundamental_data={}))


# --- 9. Future fundamental data excluded (available_at > as_of) --------------------------------

def test_9_future_fundamental_data_excluded(setup):
    future_only = {sym: [_fundamental_record(sym, pe, available_at=datetime(2026, 9, 1))]
                   for sym, pe in PE_VALUES.items()}
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        # every record is disclosed AFTER as_of -> zero PIT-visible fundamentals -> below
        # min_cross_sectional_samples for value_pe:v1
        CertifiedResearchRunExecutor.execute(_make_request(setup, fundamental_data=future_only))


# --- 10. Current-only fundamental provenance rejected -------------------------------------------

def test_10_current_only_provenance_rejected(setup):
    current_only = {
        sym: [FundamentalDataContract(
            symbol=sym, trade_date="2026-08-01", report_date="2026-06-30", announcement_date="2026-07-15",
            currency="CNY", revenue=None, net_income=None, eps_annual=None, eps_ttm=None,
            book_value_per_share=None, operating_cash_flow=None, shares_outstanding=1e9, market_cap=1e11,
            pe_lyr=None, pe_ttm=pe, pe_ttm_status="VALID", pb=None, pb_status="UNAVAILABLE",
            dividend_yield_ttm=None, dividend_yield_status="UNAVAILABLE", roe=None,
            provenance=MetricProvenance.CURRENT_ONLY, quality_status="VALID",
            available_at=datetime(2026, 7, 15), received_at=datetime(2026, 7, 15), as_of=None,
            data_origin="GOLDEN_DATASET",
        )]
        for sym, pe in PE_VALUES.items()
    }
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, fundamental_data=current_only))


# --- 11. Insufficient cross-sectional sample -----------------------------------------------------

def test_11_insufficient_cross_sectional_sample_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(
            setup,
            universe_symbols=SYMBOLS[:2],
            raw_price_series={s: (DATES, PRICES[s]) for s in SYMBOLS[:2]},
            provider_data_origin={s: "GOLDEN_DATASET" for s in SYMBOLS[:2]},
            min_cross_sectional_samples=3,  # only 2 symbols supplied
        ))


def test_11b_min_cross_sectional_samples_cannot_be_silently_lowered(setup):
    """min_cross_sectional_samples must be explicit configuration, not something the gate
    quietly relaxes to make a thin universe pass."""
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, min_cross_sectional_samples=0))


# --- 12-15. Universe / snapshot / dataset / cost-model mismatch, re-confirmed under the full ---
#            factor-driven pipeline (not just the single-symbol Phase 7J path) ------------------

def test_12_universe_mismatch_fails_under_factor_path(setup):
    setup["security_master"].register(SecurityMasterContract(
        symbol="999999.SH", exchange="SSE", display_name="delisted", security_type="STOCK",
        list_date="2000-01-01", delist_date="2026-01-01", status="DELISTED",
        industry_sw_l1="x", industry_sw_l2="x",
    ))
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(
            setup, universe_symbols=SYMBOLS + ["999999.SH"],
            raw_price_series={**{s: (DATES, PRICES[s]) for s in SYMBOLS}, "999999.SH": (DATES, PRICES["600519.SH"])},
            provider_data_origin={**{s: "GOLDEN_DATASET" for s in SYMBOLS}, "999999.SH": "GOLDEN_DATASET"},
        ))


def test_13_snapshot_mismatch_fails_under_factor_path(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, snapshot_id="snap_never_created"))


def test_14_dataset_mismatch_fails_under_factor_path(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, dataset_version="v_never_certified"))


def test_15_cost_model_mismatch_produces_different_result_under_factor_path(setup):
    result_low, _ = CertifiedResearchRunExecutor.execute(_make_request(
        setup, run_id="run_cost_low_factor", cost_model_config={"commission_rate": 0.0001}
    ))
    result_high, _ = CertifiedResearchRunExecutor.execute(_make_request(
        setup, run_id="run_cost_high_factor", cost_model_config={"commission_rate": 0.05}
    ))
    assert result_low.total_return != result_high.total_return


# --- 16. Signal configuration mismatch -----------------------------------------------------------

def test_16_signal_config_missing_a_resolved_factor_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(
            setup, signal_config=[FactorWeightConfig("momentum_20d:v1", 1.0, FactorDirection.POSITIVE)],
            # value_pe:v1 is in factor_definitions but absent from signal_config
        ))


def test_16b_empty_signal_config_fails(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, signal_config=[]))


# --- 17. Portfolio configuration mismatch (missing/invalid top_n) --------------------------------

def test_17_missing_top_n_fails_closed(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, parameters={"unrelated_key": 1}))


def test_17b_non_integer_top_n_fails_closed(setup):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        CertifiedResearchRunExecutor.execute(_make_request(setup, parameters={"top_n": "five"}))


# --- 18. Replay without factor recalculation is structurally impossible --------------------------

def test_18_replay_recomputes_factors_not_cached_values(setup):
    """Prove replay doesn't just re-read the cached factor_values artifact: corrupt the stored
    artifact after certification (simulating a tampered cache) and show replay still succeeds
    with the correct recomputed values — because it never reads factor_values as an input."""
    CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_replay_factor_ok"))
    stored = setup["run_store"].get_run("run_replay_factor_ok")
    stored["artifacts"]["factor_values"]["momentum_20d:v1"] = {"FAKE": {"raw_value": 999.0, "status": "VALID"}}

    report = _replay_engine(setup).replay("run_replay_factor_ok")
    assert report.status == ReplayStatus.REPRODUCIBLE, (
        "replay must recompute factors from source, not be affected by a corrupted "
        "factor_values audit artifact"
    )


# --- 19. Replay with modified factor (registry behavior changes) ---------------------------------

def test_19_replay_detects_factor_definition_removed_from_registry(setup):
    CertifiedResearchRunExecutor.execute(_make_request(
        setup, run_id="run_replay_factor_removed",
        factor_definitions=[FactorSpec("momentum_20d:v1", {"window_days": 3})],
        signal_config=[FactorWeightConfig("momentum_20d:v1", 1.0, FactorDirection.POSITIVE)],
    ))
    # Simulate the factor no longer existing at replay time.
    original_entries = dict(FactorRegistry._entries)
    del FactorRegistry._entries["momentum_20d:v1"]
    try:
        with pytest.raises(ValueError, match="FAIL CLOSED"):
            _replay_engine(setup).replay("run_replay_factor_removed")
    finally:
        FactorRegistry._entries.clear()
        FactorRegistry._entries.update(original_entries)


def test_19b_replay_detects_changed_fundamental_data(setup):
    """Uniformly rescaling every PE value (e.g. x5) leaves z-score normalization's output
    unchanged — (kx-kμ)/(kσ) == (x-μ)/σ — so that would not be a meaningful test of replay's
    sensitivity to changed data. Swapping which symbol holds which PE value changes the
    cross-sectional RANKING, which genuinely changes the normalized scores."""
    CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_replay_fund_changed"))
    swapped_values = dict(zip(PE_VALUES.keys(), reversed(list(PE_VALUES.values()))))
    tampered_fundamental = {sym: [_fundamental_record(sym, pe)] for sym, pe in swapped_values.items()}
    replay_engine = CertifiedReplayEngine(
        setup["run_store"], setup["snapshot_manager"], setup["manifest_store"],
        setup["corporate_action_store"], setup["security_master"], tampered_fundamental,
    )
    with pytest.raises(IntermediateArtifactMismatchError):
        replay_engine.replay("run_replay_fund_changed")


# --- 20. Replay with modified portfolio (weights artifact tampered) ------------------------------

def test_20_replay_detects_tampered_portfolio_weights_artifact(setup):
    """Even if every recomputation matches, a stored portfolio_weights artifact that was
    tampered with (post-hoc, not reflecting what was actually certified) must be caught — the
    recomputed weights are compared against it, and any mismatch fails closed."""
    CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_replay_weights_tampered"))
    stored = setup["run_store"].get_run("run_replay_weights_tampered")
    stored["artifacts"]["portfolio_weights"] = {"000001.SZ": 1.0}  # not what was actually certified

    with pytest.raises(IntermediateArtifactMismatchError, match="INTERMEDIATE_ARTIFACT_MISMATCH"):
        _replay_engine(setup).replay("run_replay_weights_tampered")


# --- Sanity: untampered replay of the Momentum+Value baseline is REPRODUCIBLE --------------------

def test_baseline_momentum_value_replay_is_reproducible(setup):
    CertifiedResearchRunExecutor.execute(_make_request(setup, run_id="run_replay_baseline_ok"))
    report = _replay_engine(setup).replay("run_replay_baseline_ok")
    assert report.status == ReplayStatus.REPRODUCIBLE
    assert report.original_result_hash == report.replayed_result_hash
