"""
test_research_application_layer.py — Phase 8R Application Layer tests (CEO directive
CEO-2026-08-03-PHASE-8R-IMPLEMENT §4/§14 item 2, §13 item E "Replay").

Proves the Application Layer's public functions genuinely drive Phase 8A's certified path
(create/get/list/replay/report) and fail closed on invalid input — using the real GOLDEN_DATASET
seed and the real CertifiedResearchRunExecutor/CertifiedReplayEngine, not a stand-in.
"""

import os
import shutil
from datetime import date

import pytest

from src.app import research_application as app

TEST_RESEARCH_DIR = "data/research"
TEST_MANIFEST_DIR = "data/manifests"


@pytest.fixture(autouse=True)
def _isolate_workbench(tmp_path, monkeypatch):
    """Points the workbench at a throwaway tmp_path directory for every test, so tests never
    touch the real data/research/ the live app uses, and resets the process-lifetime singleton
    context between tests."""
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


# --- 1/4: available dataset / factor definitions ------------------------------------------------

def test_get_available_datasets_returns_golden_dataset_never_real_provider():
    datasets = app.get_available_datasets()
    assert len(datasets) == 1
    assert datasets[0].data_origin == "GOLDEN_DATASET"
    assert datasets[0].content_sha256


def test_get_factor_definitions_returns_only_certified_factors():
    factors = {f.factor_id for f in app.get_factor_definitions()}
    assert factors == {"momentum_20d:v1", "value_pe:v1"}


# --- 3: universe -----------------------------------------------------------------------------

def test_get_universe_reflects_pit_tradability():
    as_of_range = app.get_available_as_of_range()
    max_as_of = date.fromisoformat(as_of_range["max_as_of"])
    universe = app.get_universe(max_as_of)
    assert all(s.tradable_as_of for s in universe.symbols)
    assert "not today's current listing" in universe.note


# --- 5/6: build + execute a certified research run -----------------------------------------------

def test_create_research_run_produces_full_certified_detail():
    detail = app.create_research_run(_default_params())
    assert detail.certification_status == "CERTIFIED"
    assert detail.dataset_sha256
    assert detail.factor_definition_hash
    assert detail.signal_configuration_hash != "NOT_APPLICABLE"
    assert detail.portfolio_weights  # momentum+value on 4 symbols, top_n=2, should select something
    assert detail.result_hash
    assert any("Live provider" in item for item in detail.limitations)
    assert any("do not guarantee future performance" in item for item in detail.limitations)


def test_create_research_run_single_factor_selection_produces_different_portfolio():
    momentum_only = app.create_research_run(_default_params(factor_ids=["momentum_20d:v1"], run_id="run_mom"))
    value_only = app.create_research_run(_default_params(factor_ids=["value_pe:v1"], run_id="run_val"))
    assert momentum_only.portfolio_weights != value_only.portfolio_weights
    assert momentum_only.factor_definition_hash != value_only.factor_definition_hash


# --- 7/9: query -------------------------------------------------------------------------------

def test_get_research_run_matches_creation_result():
    created = app.create_research_run(_default_params())
    fetched = app.get_research_run(created.run_id)
    assert fetched == created


def test_get_research_run_unknown_id_fails_closed():
    with pytest.raises(app.ResearchRunError):
        app.get_research_run("run_does_not_exist")


def test_list_research_runs_includes_created_run():
    created = app.create_research_run(_default_params())
    ids = [r.run_id for r in app.list_research_runs()]
    assert created.run_id in ids


# --- 8: replay --------------------------------------------------------------------------------

def test_replay_research_run_is_reproducible_when_untampered():
    created = app.create_research_run(_default_params())
    replay = app.replay_research_run(created.run_id)
    assert replay.status == "REPRODUCIBLE"
    assert replay.original_result_hash == replay.replayed_result_hash


# --- 10: provenance / integrity ------------------------------------------------------------------

def test_get_integrity_report_shows_golden_dataset_and_not_verified_live_provider():
    created = app.create_research_run(_default_params())
    report = app.get_integrity_report(created.run_id)
    assert set(report.provider_data_origin.values()) == {"GOLDEN_DATASET"}
    assert "NOT VERIFIED" in report.live_provider_status
    assert "TUSHARE_TOKEN" in report.live_provider_status


# --- Report export ----------------------------------------------------------------------------

def test_generate_research_report_includes_required_sections_and_disclaimer():
    created = app.create_research_run(_default_params())
    report_md = app.generate_research_report(created.run_id)
    for heading in ["Executive Summary", "Factor Analysis", "Portfolio", "Backtest", "Integrity", "Limitations"]:
        assert heading in report_md
    assert "do not guarantee future performance" in report_md
    assert "not a live or trading portfolio" in report_md
    assert "not investment advice" in report_md


# --- Fail-closed input validation (directive §13 item F, exercised via the Application Layer) ----

def test_empty_universe_fails_closed():
    with pytest.raises(app.ResearchRunError, match="FAIL CLOSED"):
        app.create_research_run(_default_params(universe_symbols=[]))


def test_unknown_symbol_in_universe_fails_closed():
    with pytest.raises(app.ResearchRunError, match="FAIL CLOSED"):
        app.create_research_run(_default_params(universe_symbols=["999999.SH"]))


def test_empty_factor_selection_fails_closed():
    with pytest.raises(app.ResearchRunError):
        app.create_research_run(_default_params(factor_ids=[]))


def test_invalid_top_n_fails_closed():
    with pytest.raises(app.ResearchRunError):
        app.create_research_run(_default_params(top_n=0))


def test_duplicate_run_id_fails_closed():
    app.create_research_run(_default_params(run_id="run_dup"))
    with pytest.raises(app.ResearchRunError):
        app.create_research_run(_default_params(run_id="run_dup"))
