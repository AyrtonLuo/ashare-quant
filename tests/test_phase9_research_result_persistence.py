"""
test_phase9_research_result_persistence.py — Phase 9 (Research Result Persistence Hardening)
tests, per PHASE_9_RESEARCH_RESULT_PERSISTENCE_ARCHITECTURE_PROPOSAL.md §16.

Proves: ResearchResultManifest's new scalar fields survive a real cross-process round-trip
with exact numerical fidelity; result_hash's definition is unchanged; Replay never reads the
new fields as a computation input; ResearchRunStore.create_run() is now atomic (no partial
writes visible under a run_id, safe under a same-run_id race); get_run() fails closed with a
clear error on a corrupted file instead of an opaque JSONDecodeError; a schema_version "1.0"
(legacy) run loads with the new fields as None, never fabricated as 0.0.
"""

import json
import os
import threading
from datetime import date, datetime

import pytest

from src.quant.reproducibility.store import ResearchRunStore
from src.quant.reproducibility.manifest import ResearchInputManifest, ResearchResultManifest
from src.quant.reproducibility.identity import ResearchRunIdentity, verify_result_manifest_integrity
from src.quant.reproducibility.canonical import compute_canonical_sha256
from src.app import research_application as app


# =================================================================================================
# Fixtures / helpers
# =================================================================================================

@pytest.fixture(autouse=True)
def _isolate_workbench(tmp_path, monkeypatch):
    research_dir = str(tmp_path / "research")
    manifest_dir = str(tmp_path / "manifests")
    run_store_dir = str(tmp_path / "research" / "runs")
    metrics_dir = str(tmp_path / "research" / "workbench_metrics")
    monkeypatch.setattr(app, "RESEARCH_BASE_DIR", research_dir)
    monkeypatch.setattr(app, "MANIFEST_BASE_DIR", manifest_dir)
    monkeypatch.setattr(app, "RUN_STORE_BASE_DIR", run_store_dir)
    monkeypatch.setattr(app, "_WORKBENCH_METRICS_DIR", metrics_dir)
    app.reset_workbench_context()
    yield
    app.reset_workbench_context()


def _default_params(**overrides):
    as_of_range = app.get_available_as_of_range()
    max_as_of = date.fromisoformat(as_of_range["max_as_of"])
    universe = app.get_universe(max_as_of)
    base = dict(
        as_of=max_as_of, universe_symbols=[s.symbol for s in universe.symbols],
        factor_ids=["momentum_20d:v1", "value_pe:v1"], top_n=2,
    )
    base.update(overrides)
    return app.ResearchRunParams(**base)


def _identity_kwargs(**overrides):
    base = dict(
        research_run_id="run_x", snapshot_id="snap_1", dataset_version="v1",
        dataset_manifest_hash="h1", as_of="2026-01-01T00:00:00", start_date="2026-01-01",
        end_date="2026-01-02", universe_definition={"symbols": ["A"]}, universe_hash="uh1",
        strategy_id="s1", strategy_version="1.0", factor_definition_hash="fh1",
        parameter_hash="ph1", transaction_cost_model_hash="ch1", benchmark_id="b1",
        code_version="c1", code_state="CLEAN", input_hash="ih1", result_hash="rh1",
        created_at="2026-01-01T00:00:00",
    )
    base.update(overrides)
    return base


def _input_manifest_kwargs(**overrides):
    base = dict(
        research_run_id="run_x", dataset_id="ds1", dataset_version="v1", snapshot_id="snap_1",
        dataset_manifest_hash="h1", as_of="2026-01-01T00:00:00", start_date="2026-01-01",
        end_date="2026-01-02", universe_type="A_SHARE", universe_symbols=["A"], universe_hash="uh1",
        factors_config=[], factor_definition_hash="fh1", strategy_id="s1", strategy_version="1.0",
        strategy_parameters={}, parameter_hash="ph1", portfolio_constraints={},
        cost_model_config={}, transaction_cost_model_hash="ch1", benchmark_id="b1",
        benchmark_version="1.0", benchmark_hash="bh1", code_version="c1", code_state="CLEAN",
        created_at="2026-01-01T00:00:00",
    )
    base.update(overrides)
    return base


# =================================================================================================
# 1. Unit — serialization round-trip
# =================================================================================================

def test_unit_result_manifest_new_fields_round_trip_through_canonical_json():
    manifest = ResearchResultManifest(
        research_run_id="run_1", input_manifest_hash="ih", result_hash="rh",
        equity_curve_hash="eh", schema_version="2.0",
        total_return=0.0519, annualized_return=0.5451, annualized_volatility=0.0851,
        sharpe_ratio=6.4029, max_drawdown=0.0063, win_rate=0.6667, turnover=0.15, trade_count=4,
    )
    from dataclasses import asdict
    from src.quant.reproducibility.canonical import to_canonical_json
    reloaded_dict = json.loads(to_canonical_json(asdict(manifest)))
    reloaded = ResearchResultManifest(**reloaded_dict)
    assert reloaded == manifest


def test_unit_legacy_manifest_without_new_fields_still_constructs():
    """A pre-Phase-9 constructor call (only the original 4 required fields) must still work —
    proves the new fields are genuinely backward-compatible trailing defaults."""
    manifest = ResearchResultManifest(
        research_run_id="run_legacy", input_manifest_hash="ih", result_hash="rh", equity_curve_hash="eh",
    )
    assert manifest.schema_version == "1.0"
    assert manifest.total_return is None
    assert manifest.sharpe_ratio is None


# =================================================================================================
# 2. Numerical truth
# =================================================================================================

def test_numerical_truth_real_backtest_precision_survives_disk_round_trip(tmp_path):
    """BacktestEngine rounds every scalar result field to 4 decimal places before constructing
    BacktestResult (src/quant/backtest/engine.py: round(total_ret, 4) etc.) — a 4-decimal value
    is exactly representable within ResearchRunStore's existing 6-decimal canonicalization
    (to_canonical_json, applied to the whole manifest since Phase 7A), so it survives the round
    trip bit-for-bit. This uses a realistic value (matching BacktestEngine's own precision), not
    an artificial one — see test_..._documents_existing_six_decimal_canonicalization_ceiling
    below for the documented edge case this does NOT cover."""
    store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    realistic_value = 0.3333  # 4-decimal precision, matching BacktestEngine's round(x, 4)

    identity = ResearchRunIdentity(**_identity_kwargs(research_run_id="run_precise"))
    input_manifest = ResearchInputManifest(**_input_manifest_kwargs(research_run_id="run_precise"))
    result_manifest = ResearchResultManifest(
        research_run_id="run_precise", input_manifest_hash="ih", result_hash="rh",
        equity_curve_hash="eh", schema_version="2.0",
        total_return=realistic_value, annualized_return=realistic_value, annualized_volatility=realistic_value,
        sharpe_ratio=realistic_value, max_drawdown=realistic_value, win_rate=realistic_value,
        turnover=realistic_value, trade_count=3,
    )
    store.create_run(identity, input_manifest, result_manifest)

    fresh_store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    reloaded = fresh_store.get_run("run_precise")["result_manifest"]
    assert reloaded.total_return == realistic_value, "exact == required, not pytest.approx — must be bit-identical for real (4-decimal) BacktestEngine output"
    assert reloaded.sharpe_ratio == realistic_value


def test_numerical_truth_documents_existing_six_decimal_canonicalization_ceiling(tmp_path):
    """DISCLOSED FINDING (not a Phase 9 regression — a pre-existing, project-wide behavior of
    to_canonical_json, in place since Phase 7I, that this proposal's own precision-policy
    section (§11) inaccurately described as 'full IEEE-754 double precision preserved... no
    additional rounding'). ResearchRunStore.create_run() writes the WHOLE manifest via
    to_canonical_json, which rounds every float to 6 decimal places as part of this project's
    standard canonicalization — not just the small result_hash payload. This is harmless in
    practice because BacktestEngine already rounds every scalar to 4 decimals before Phase 9's
    fields are ever populated (4-decimal values are exactly representable at 6-decimal
    precision), but a value requiring MORE than 6 decimals of precision (never produced by this
    codebase's own BacktestEngine) would NOT survive with full fidelity. Documented here rather
    than silently left for someone to discover later."""
    store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    high_precision_value = 1.0 / 3.0  # 0.3333333333333333... — more precise than 6 decimals

    identity = ResearchRunIdentity(**_identity_kwargs(research_run_id="run_edge"))
    input_manifest = ResearchInputManifest(**_input_manifest_kwargs(research_run_id="run_edge"))
    result_manifest = ResearchResultManifest(
        research_run_id="run_edge", input_manifest_hash="ih", result_hash="rh",
        equity_curve_hash="eh", schema_version="2.0",
        total_return=high_precision_value, annualized_return=0.0, annualized_volatility=0.0,
        sharpe_ratio=0.0, max_drawdown=0.0, win_rate=0.0, turnover=0.0, trade_count=1,
    )
    store.create_run(identity, input_manifest, result_manifest)

    fresh_store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    reloaded = fresh_store.get_run("run_edge")["result_manifest"]
    assert reloaded.total_return == round(high_precision_value, 6)
    assert reloaded.total_return != high_precision_value  # documents the ceiling, not a bug


def test_numerical_truth_certified_run_matches_direct_result_object():
    detail = app.create_research_run(_default_params())
    ctx = app.get_workbench_context()
    fresh_store = ResearchRunStore(base_dir=ctx.run_store.base_dir)
    reloaded = fresh_store.get_run(detail.run_id)["result_manifest"]
    assert reloaded.total_return == detail.total_return
    assert reloaded.sharpe_ratio == detail.sharpe_ratio
    assert reloaded.max_drawdown == detail.max_drawdown


# =================================================================================================
# 3. Identity stability (existing tests, unmodified, are the proof — see full suite run)
# =================================================================================================

def test_identity_result_hash_definition_is_unchanged():
    """result_hash must still be computed over exactly {"sharpe","return","mdd"} — proves this
    proposal did not redefine what the hash covers. Derives the expected payload from the run's
    own detail object (not hardcoded literals) so this test stays valid across any legitimate
    change to the certified numeric output — e.g. CORPORATE_ACTION_UNIFIED_FORMULA_ARCHITECTURE_
    PROPOSAL.md's "2.0" formula, which changed golden-dataset numbers versus the "1.0"-era
    literals this test used to hardcode — without weakening what it actually proves."""
    detail = app.create_research_run(_default_params())
    expected = compute_canonical_sha256({
        "sharpe": detail.sharpe_ratio, "return": detail.total_return, "mdd": detail.max_drawdown,
    })
    assert detail.result_hash == expected


# =================================================================================================
# 4. Hash stability / integrity
# =================================================================================================

def test_integrity_check_passes_for_untampered_run():
    detail = app.create_research_run(_default_params())
    ctx = app.get_workbench_context()
    run_data = ctx.run_store.get_run(detail.run_id)
    assert verify_result_manifest_integrity(run_data["identity"], run_data["result_manifest"]) is True


def test_integrity_check_fails_after_direct_tampering(tmp_path):
    store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    identity = ResearchRunIdentity(
        **_identity_kwargs(research_run_id="run_tamper", result_hash=compute_canonical_sha256(
            {"sharpe": 1.0, "return": 0.1, "mdd": 0.05}
        ))
    )
    input_manifest = ResearchInputManifest(**_input_manifest_kwargs(research_run_id="run_tamper"))
    result_manifest = ResearchResultManifest(
        research_run_id="run_tamper", input_manifest_hash="ih", result_hash=identity.result_hash,
        equity_curve_hash="eh", schema_version="2.0",
        total_return=0.1, annualized_return=0.1, annualized_volatility=0.1,
        sharpe_ratio=1.0, max_drawdown=0.05, win_rate=0.5, turnover=0.1, trade_count=1,
    )
    store.create_run(identity, input_manifest, result_manifest)

    # Directly tamper with the persisted file, independent of run_metadata.json.
    result_path = os.path.join(str(tmp_path / "runs"), "run_tamper", "result_manifest.json")
    with open(result_path, "r") as f:
        data = json.load(f)
    data["sharpe_ratio"] = 999.0
    with open(result_path, "w") as f:
        json.dump(data, f)

    fresh_store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    run_data = fresh_store.get_run("run_tamper")
    assert verify_result_manifest_integrity(run_data["identity"], run_data["result_manifest"]) is False


def test_integrity_check_returns_false_not_exception_for_legacy_schema():
    identity = ResearchRunIdentity(**_identity_kwargs())
    legacy_manifest = ResearchResultManifest(
        research_run_id="run_x", input_manifest_hash="ih", result_hash="rh", equity_curve_hash="eh",
    )
    assert verify_result_manifest_integrity(identity, legacy_manifest) is False


# =================================================================================================
# 5. Cross-process
# =================================================================================================

def test_cross_process_fresh_store_instance_reads_real_metrics():
    detail = app.create_research_run(_default_params())
    ctx = app.get_workbench_context()
    # A brand-new ResearchRunStore object, same base_dir, simulating a fresh process — this
    # codebase's existing convention for cross-process testing (the store is stateless-on-disk).
    fresh_store = ResearchRunStore(base_dir=ctx.run_store.base_dir)
    result_manifest = fresh_store.get_result_manifest(detail.run_id)
    assert result_manifest.total_return == detail.total_return
    assert result_manifest.schema_version == "2.0"


# =================================================================================================
# 6. Replay — never reads the new fields as a computation input
# =================================================================================================

def test_replay_still_reproducible_with_new_manifest_fields_present():
    detail = app.create_research_run(_default_params())
    replay = app.replay_research_run(detail.run_id)
    assert replay.status == "REPRODUCIBLE"


def test_replay_source_never_references_result_manifest_scalar_fields():
    """Static check: CertifiedReplayEngine.replay's source never reads total_return/sharpe_ratio/
    etc. from the stored result_manifest as an input — it always recomputes them fresh via
    BacktestEngine and compares only the hash."""
    import inspect
    from src.quant.reproducibility.certified_replay_engine import CertifiedReplayEngine
    source = inspect.getsource(CertifiedReplayEngine.replay)
    for forbidden in ["result_manifest.total_return", "result_manifest.sharpe_ratio", "result_manifest.max_drawdown"]:
        assert forbidden not in source


# =================================================================================================
# 7. Corruption
# =================================================================================================

def test_corrupted_result_manifest_fails_closed_with_clear_error(tmp_path):
    store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    identity = ResearchRunIdentity(**_identity_kwargs(research_run_id="run_corrupt"))
    input_manifest = ResearchInputManifest(**_input_manifest_kwargs(research_run_id="run_corrupt"))
    result_manifest = ResearchResultManifest(
        research_run_id="run_corrupt", input_manifest_hash="ih", result_hash="rh", equity_curve_hash="eh",
    )
    store.create_run(identity, input_manifest, result_manifest)

    result_path = os.path.join(str(tmp_path / "runs"), "run_corrupt", "result_manifest.json")
    with open(result_path, "w") as f:
        f.write("{not valid json!!!")

    fresh_store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    with pytest.raises(RuntimeError, match="FAIL CLOSED"):
        fresh_store.get_run("run_corrupt")


# =================================================================================================
# 8. Compatibility — old-shape (schema_version "1.0") runs load without fabricating values
# =================================================================================================

def test_legacy_run_directory_without_schema_version_loads_with_none_metrics(tmp_path):
    """Simulates a run persisted before Phase 9 existed: result_manifest.json on disk has only
    the original 4 fields, no schema_version, no scalar metrics keys at all."""
    run_dir = tmp_path / "runs" / "run_pre_phase9"
    run_dir.mkdir(parents=True)
    from dataclasses import asdict
    from src.quant.reproducibility.canonical import to_canonical_json

    identity = ResearchRunIdentity(**_identity_kwargs(research_run_id="run_pre_phase9"))
    input_manifest = ResearchInputManifest(**_input_manifest_kwargs(research_run_id="run_pre_phase9"))
    legacy_result_dict = {
        "research_run_id": "run_pre_phase9", "input_manifest_hash": "ih",
        "result_hash": "rh", "equity_curve_hash": "eh",
        "positions_hash": "UNAVAILABLE", "trades_hash": "UNAVAILABLE", "signals_hash": "UNAVAILABLE",
        "factor_output_hash": "UNAVAILABLE", "performance_metrics_hash": "UNAVAILABLE",
        "drawdown_hash": "UNAVAILABLE", "benchmark_result_hash": "UNAVAILABLE",
    }
    (run_dir / "run_metadata.json").write_text(to_canonical_json(asdict(identity)))
    (run_dir / "input_manifest.json").write_text(to_canonical_json(asdict(input_manifest)))
    (run_dir / "result_manifest.json").write_text(json.dumps(legacy_result_dict))

    store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    run_data = store.get_run("run_pre_phase9")
    result_manifest = run_data["result_manifest"]
    assert result_manifest.schema_version == "1.0"
    assert result_manifest.total_return is None, "legacy run must read as None, never fabricated as 0.0"
    assert result_manifest.sharpe_ratio is None


# =================================================================================================
# 9b. Application Layer migration (deferred item resolved: get_research_run() prefers canonical
#     result_manifest fields; workbench_metrics/ remains a fallback for legacy runs only)
# =================================================================================================

def test_get_research_run_falls_back_to_workbench_metrics_for_legacy_schema_version(tmp_path):
    """A run persisted before Phase 9 (schema_version == "1.0", no canonical scalar fields) has
    no canonical metrics to read — get_research_run() must fall back to the legacy
    workbench_metrics/ side cache for it, exactly as it did before this migration, rather than
    fabricating 0.0 or erroring."""
    ctx = app.get_workbench_context()
    identity = ResearchRunIdentity(**_identity_kwargs(research_run_id="run_legacy_app"))
    input_manifest = ResearchInputManifest(**_input_manifest_kwargs(research_run_id="run_legacy_app"))
    legacy_result_manifest = ResearchResultManifest(
        research_run_id="run_legacy_app", input_manifest_hash="ih", result_hash="rh", equity_curve_hash="eh",
    )
    ctx.run_store.create_run(identity, input_manifest, legacy_result_manifest)

    os.makedirs(app._WORKBENCH_METRICS_DIR, exist_ok=True)
    with open(os.path.join(app._WORKBENCH_METRICS_DIR, "run_legacy_app.json"), "w") as f:
        json.dump({
            "total_return": 0.0777, "annualized_return": 0.1111, "annualized_volatility": 0.2222,
            "sharpe_ratio": 0.9999, "max_drawdown": 0.0333, "win_rate": 0.5,
        }, f)

    detail = app.get_research_run("run_legacy_app")
    assert detail.total_return == 0.0777
    assert detail.sharpe_ratio == 0.9999
    assert detail.max_drawdown == 0.0333


def test_get_research_run_prefers_canonical_fields_over_stale_workbench_metrics_cache():
    """If both a canonical (schema_version 2.0) result_manifest and a workbench_metrics/ cache
    exist for the same run (e.g. a stale cache left over from a re-run), the canonical fields
    must win — proves this isn't merely 'read whichever is present' but a real preference order."""
    detail = app.create_research_run(_default_params())
    ctx = app.get_workbench_context()

    stale_path = os.path.join(app._WORKBENCH_METRICS_DIR, f"{detail.run_id}.json")
    with open(stale_path, "w") as f:
        json.dump({
            "total_return": -99.0, "annualized_return": -99.0, "annualized_volatility": -99.0,
            "sharpe_ratio": -99.0, "max_drawdown": -99.0, "win_rate": -99.0,
        }, f)

    reread = app.get_research_run(detail.run_id)
    assert reread.total_return == detail.total_return
    assert reread.total_return != -99.0


# =================================================================================================
# 9. Concurrency
# =================================================================================================

def test_concurrent_create_run_same_id_exactly_one_wins(tmp_path):
    store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    identity = ResearchRunIdentity(**_identity_kwargs(research_run_id="run_race"))
    input_manifest = ResearchInputManifest(**_input_manifest_kwargs(research_run_id="run_race"))
    result_manifest = ResearchResultManifest(
        research_run_id="run_race", input_manifest_hash="ih", result_hash="rh", equity_curve_hash="eh",
    )

    results = []

    def attempt():
        try:
            store.create_run(identity, input_manifest, result_manifest)
            results.append("success")
        except ValueError:
            results.append("fail_closed")
        except Exception as e:
            results.append(f"unexpected:{e}")

    threads = [threading.Thread(target=attempt) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("success") == 1, f"exactly one attempt must succeed, got: {results}"
    assert results.count("fail_closed") == 4
    assert all(not r.startswith("unexpected") for r in results)

    # No orphaned .tmp-* directories should survive a clean run.
    leftover_tmp_dirs = [d for d in os.listdir(str(tmp_path / "runs")) if ".tmp-" in d]
    assert leftover_tmp_dirs == []

    # The final directory must contain a complete, uncorrupted run.
    fresh_store = ResearchRunStore(base_dir=str(tmp_path / "runs"))
    loaded = fresh_store.get_run("run_race")
    assert loaded is not None
    assert loaded["result_manifest"].research_run_id == "run_race"


# =================================================================================================
# 10. Corporate Action Unified Formula — adjustment_algorithm_version (CEO-approved implementation)
# =================================================================================================

def test_input_manifest_adjustment_algorithm_version_defaults_to_legacy():
    """An old-style construction call (predating this field, exactly _input_manifest_kwargs()'s
    shape) must still work and default to "1.0" — never silently assumed to be "2.0"."""
    manifest = ResearchInputManifest(**_input_manifest_kwargs(research_run_id="run_legacy_algo"))
    assert manifest.adjustment_algorithm_version == "1.0"


def test_input_hash_changes_when_adjustment_algorithm_version_differs():
    """adjustment_algorithm_version must participate in compute_input_hash() like every other
    input field — a run's certified algorithm choice is itself part of what's certified."""
    manifest_1_0 = ResearchInputManifest(
        **_input_manifest_kwargs(research_run_id="run_algo_cmp", adjustment_algorithm_version="1.0")
    )
    manifest_2_0 = ResearchInputManifest(
        **_input_manifest_kwargs(research_run_id="run_algo_cmp", adjustment_algorithm_version="2.0")
    )
    assert manifest_1_0.compute_input_hash() != manifest_2_0.compute_input_hash()
