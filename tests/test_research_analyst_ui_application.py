"""
test_research_analyst_ui_application.py — AI Research Analyst Step 6: Application Layer + UI
(AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §9 / §11 step 6).

The UI itself is a Streamlit script and is verified structurally (AST/source), exactly as the
Phase 8R boundary tests already verify it: no Streamlit import may exist outside
streamlit_app.py, and the UI may reach project code only through the Application Layer. The
behaviour the UI renders is tested directly against the Application Layer, which is where all of
it is produced.
"""

import ast
import json
import os
import re

import pytest

from src.app import research_analyst_application as analyst
from src.app import research_application as app

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "app")
UI_FILE = os.path.join(APP_DIR, "streamlit_app.py")
ANALYST_APP_FILE = os.path.join(APP_DIR, "research_analyst_application.py")

SYMBOL = "600519.SH"


@pytest.fixture(autouse=True)
def _isolated_report_store(tmp_path):
    analyst.reset_report_store(base_dir=str(tmp_path / "analyst_reports"))
    yield
    analyst.reset_report_store()


@pytest.fixture()
def as_of():
    return app.get_available_as_of_range()["max_as_of"]


def _generate(as_of, symbol=SYMBOL, **kwargs):
    return analyst.generate_analyst_report(
        symbol, as_of, allow_synthetic_narrative=True, **kwargs
    )


# --- Architecture boundary -------------------------------------------------------------------

def _source(path):
    with open(path, "r") as f:
        return f.read()


def test_streamlit_is_imported_only_by_the_ui_file():
    for name in os.listdir(APP_DIR):
        if not name.endswith(".py") or name == "streamlit_app.py":
            continue
        assert "import streamlit" not in _source(os.path.join(APP_DIR, name)), name


def _imported_modules(path):
    tree = ast.parse(_source(path), filename=path)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.update(f"{node.module}.{a.name}" for a in node.names)
            modules.add(node.module)
    return modules


def test_analyst_application_layer_imports_no_ui_framework():
    """AST-based, not a substring scan: this module's own docstring discusses Streamlit's
    boundary in prose, and prose is not an import."""
    modules = {m.split(".")[0] for m in _imported_modules(ANALYST_APP_FILE)}
    assert not (modules & {"streamlit", "flask", "fastapi", "jinja2"})


def test_ui_reaches_project_code_only_through_the_application_layer():
    tree = ast.parse(_source(UI_FILE), filename=UI_FILE)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.update(f"{node.module}.{a.name}" for a in node.names)
            imported.add(node.module)
    project = {m for m in imported if m.startswith("src.") and m != "src.app"}
    assert project == {
        "src.app.research_application", "src.app.research_analyst_application",
    }


def test_ui_never_calls_an_llm_or_evidence_internal_directly():
    tree = ast.parse(_source(UI_FILE), filename=UI_FILE)
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)
    forbidden = {
        "generate_ai_research_output", "generate_research_report_layer", "validate_citations",
        "compute_data_confidence", "detect_evidence_conflicts", "assemble_market_evidence",
        "assemble_report_sections", "compute_evidence_bundle_hash", "FakeLLMProvider",
        "ResearchAnalystReportStore", "persist_research_report",
    }
    assert not (called & forbidden)


def test_analyst_application_public_functions_contain_no_trading_verbs():
    """Mirrors test_g_application_layer_public_function_names_contain_no_trading_verbs for the
    new Application Layer module. (The file-level trading-identifier sweep over src/app/ in
    test_phase_8r_security_boundary.py::test_g_* already covers both new files, and does so via
    AST identifiers rather than a substring scan that a disclaimer's prose would trip.)"""
    public = [n for n in dir(analyst)
              if not n.startswith("_") and callable(getattr(analyst, n))]
    for name in public:
        for fragment in ("order", "trade", "broker", "execute_buy", "execute_sell", "place_"):
            assert fragment not in name.lower(), name


# --- LLM provider availability is reported honestly -------------------------------------------

def test_provider_status_reports_no_live_implementation():
    status = analyst.get_llm_provider_status()
    assert status.live_provider_implemented is False
    assert status.status == "NO_LIVE_LLM_PROVIDER_IMPLEMENTED"
    assert "no live llm provider" in status.message.lower()


def test_a_present_credential_does_not_imply_a_usable_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key-0123456789")
    status = analyst.get_llm_provider_status()
    assert status.live_provider_implemented is False
    assert status.status == "NO_LIVE_LLM_PROVIDER_IMPLEMENTED"


def test_credential_reports_never_expose_the_key_value(monkeypatch):
    secret = "sk-super-secret-value-9876543210"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    status = analyst.get_llm_provider_status()
    assert secret not in json.dumps(list(status.credential_reports))
    assert secret not in status.message


# --- Evidence bundle: availability, provenance, PIT ---------------------------------------------

def test_evidence_bundle_reports_available_and_unavailable_categories(as_of):
    view = analyst.get_evidence_bundle_view(SYMBOL, as_of)
    by_category = {c.category: c for c in view.categories}

    for present in ("MARKET", "FUNDAMENTAL", "TECHNICAL"):
        assert by_category[present].available is True
        assert by_category[present].item_count > 0
        assert by_category[present].reason is None

    for absent in ("QUANT_FACTOR", "NEWS", "RISK"):
        assert by_category[absent].available is False
        assert by_category[absent].item_count == 0
        assert by_category[absent].reason  # an explicit reason, never a blank
        assert by_category[absent].data_origins == ()


def test_evidence_bundle_exposes_provenance_and_is_never_real_provider(as_of):
    view = analyst.get_evidence_bundle_view(SYMBOL, as_of)
    assert view.data_origin_breakdown == {"GOLDEN_DATASET": view.item_count}
    assert "REAL_PROVIDER" not in view.data_origin_breakdown
    assert all(i.data_origin == "GOLDEN_DATASET" for i in view.items)


def test_evidence_bundle_hash_is_deterministic(as_of):
    a = analyst.get_evidence_bundle_view(SYMBOL, as_of)
    b = analyst.get_evidence_bundle_view(SYMBOL, as_of)
    assert a.evidence_bundle_hash == b.evidence_bundle_hash
    assert len(a.evidence_bundle_hash) == 64


def test_evidence_bundle_respects_the_pit_cutoff(as_of):
    early = app.get_available_as_of_range()["min_as_of"]
    assert analyst.get_evidence_bundle_view(SYMBOL, early).item_count < \
        analyst.get_evidence_bundle_view(SYMBOL, as_of).item_count


def test_every_evidence_item_is_fact_or_model_output_never_ai(as_of):
    view = analyst.get_evidence_bundle_view(SYMBOL, as_of)
    assert {i.kind for i in view.items} <= {"FACT", "MODEL_OUTPUT"}


def test_unknown_symbol_fails_closed(as_of):
    with pytest.raises(analyst.ResearchAnalystError, match="FAIL CLOSED"):
        analyst.get_evidence_bundle_view("999999.XX", as_of)


def test_unsupported_as_of_type_fails_closed():
    with pytest.raises(analyst.ResearchAnalystError, match="FAIL CLOSED"):
        analyst.get_evidence_bundle_view(SYMBOL, 20240205)


# --- Generation: fail-closed by default ------------------------------------------------------------

def test_generation_fails_closed_without_a_live_provider(as_of):
    with pytest.raises(analyst.ResearchAnalystError) as excinfo:
        analyst.generate_analyst_report(SYMBOL, as_of)
    assert "NO_LIVE_LLM_PROVIDER_IMPLEMENTED" in str(excinfo.value)


def test_fail_closed_generation_persists_nothing(as_of):
    with pytest.raises(analyst.ResearchAnalystError):
        analyst.generate_analyst_report(SYMBOL, as_of)
    assert analyst.list_analyst_reports() == []


def test_generation_fails_closed_when_no_evidence_exists():
    """An as_of before the dataset begins yields an empty bundle — no report is invented."""
    with pytest.raises(analyst.ResearchAnalystError, match="no evidence is available"):
        analyst.generate_analyst_report(
            SYMBOL, "2000-01-01", allow_synthetic_narrative=True
        )


# --- Synthetic narrative is labelled, never passed off as analysis ------------------------------------

def test_synthetic_report_is_labelled_at_every_level(as_of):
    view = _generate(as_of)
    assert view.narrative_origin == "SYNTHETIC_DATA"
    assert view.narrative_warning and "no LLM API was called" in view.narrative_warning
    for section in view.sections:
        if section.content_type == "MODEL_OUTPUT" or section.is_missing_data:
            continue
        assert "SYNTHETIC PLACEHOLDER" in section.body


def test_synthetic_narrative_states_no_figures(as_of):
    """The placeholder prose contains no numerals, so it cannot assert a figure of any kind."""
    canned = analyst._synthetic_canned_output([])
    for key, value in canned.items():
        if key == "evidence_ids":
            continue
        assert not re.search(r"\d", value), key


def test_synthetic_origin_is_persisted_on_the_identity(as_of):
    view = _generate(as_of)
    stored = analyst.get_report_store().get_report(view.report_id)
    assert stored["identity"].data_origin == "SYNTHETIC_DATA"


# --- The rendered report: all ten sections and every required panel -------------------------------------

def test_report_view_carries_all_ten_sections(as_of):
    view = _generate(as_of)
    assert [s.number for s in view.sections] == list(range(1, 11))
    assert [s.title for s in view.sections][:5] == [
        "Executive Summary", "Technical Analysis", "Fundamental Analysis",
        "Quant Factor Analysis", "News / Event Analysis",
    ]


def test_report_view_covers_every_panel_the_directive_requires(as_of):
    view = _generate(as_of)
    titles = {s.title for s in view.sections}
    for required in ("Technical Analysis", "Fundamental Analysis", "Quant Factor Analysis",
                     "News / Event Analysis", "Bull Case", "Bear Case", "Risk Analysis",
                     "Data Confidence"):
        assert required in titles
    assert view.evidence.item_count > 0            # Evidence
    assert view.data_confidence.computed_by == "DETERMINISTIC_CODE"


def test_bull_and_bear_are_both_rendered_and_distinct(as_of):
    view = _generate(as_of)
    by_number = {s.number: s for s in view.sections}
    assert by_number[6].body.strip() and by_number[7].body.strip()
    assert by_number[6].body != by_number[7].body


def test_unavailable_categories_are_marked_in_the_rendered_sections(as_of):
    view = _generate(as_of)
    by_number = {s.number: s for s in view.sections}
    for section_number in (4, 5):  # Quant Factor, News — absent from the certified dataset
        assert by_number[section_number].is_missing_data is True
        assert by_number[section_number].body.startswith("NOT AVAILABLE")
        assert by_number[section_number].suppressed_ai_body is not None
    assert set(view.data_confidence.missing_categories) == {"QUANT_FACTOR", "NEWS", "RISK"}


def test_data_confidence_view_is_computed_and_auditable(as_of):
    dc = _generate(as_of).data_confidence
    assert dc.computed_by == "DETERMINISTIC_CODE"
    assert 0.0 <= dc.score <= 1.0
    assert dc.band in ("HIGH", "MEDIUM", "LOW")
    assert set(dc.components) <= {"origin", "coverage", "recency", "conflict"}
    assert dc.real_provider_ratio == 0.0     # GOLDEN_DATASET only, stated not hidden
    assert dc.fact_count + dc.model_output_count == view_item_count(as_of)


def view_item_count(as_of):
    return analyst.get_evidence_bundle_view(SYMBOL, as_of).item_count


def test_report_view_carries_disclaimer_and_limitations(as_of):
    view = _generate(as_of)
    assert "not investment advice" in view.disclaimer.lower()
    joined = " ".join(view.limitations)
    assert "No live LLM provider implementation exists" in joined
    assert "GOLDEN_DATASET" in joined
    assert "bit-reproducible" in joined


def test_report_view_exposes_reproducibility_scope_and_provenance(as_of):
    view = _generate(as_of)
    assert "AI_PROSE_NOT_BIT_REPRODUCIBLE" in view.reproducibility_scope
    assert view.evidence_bundle_hash == view.evidence.evidence_bundle_hash
    assert view.prompt_version == "synthetic-1.0"
    assert view.code_state in ("CLEAN", "DIRTY", "UNAVAILABLE")


def test_markdown_download_payload_is_complete(as_of):
    view = _generate(as_of)
    for section in view.sections:
        assert f"## {section.number}. {section.title}" in view.markdown
    assert view.evidence_bundle_hash in view.markdown


# --- Persistence round trip -------------------------------------------------------------------------------

def test_persisted_report_is_listed_and_reloadable(as_of):
    view = _generate(as_of)
    summaries = analyst.list_analyst_reports()
    assert [s.report_id for s in summaries] == [view.report_id]
    assert summaries[0].symbol == SYMBOL
    assert summaries[0].narrative_origin == "SYNTHETIC_DATA"

    reloaded = analyst.get_analyst_report(view.report_id)
    assert reloaded.report_id == view.report_id
    assert len(reloaded.sections) == 10
    assert reloaded.evidence_bundle_hash == view.evidence_bundle_hash
    assert [s.body for s in reloaded.sections] == [s.body for s in view.sections]


def test_reloaded_report_verifies_its_evidence_integrity(as_of):
    view = _generate(as_of)
    assert analyst.get_analyst_report(view.report_id).evidence_integrity_verified is True


def test_tampered_evidence_is_reported_as_failing_integrity(as_of, tmp_path):
    view = _generate(as_of)
    store = analyst.get_report_store()
    bundle_path = os.path.join(store.base_dir, view.report_id, "evidence_bundle.json")
    with open(bundle_path) as f:
        payload = json.load(f)
    payload[0]["content"] = {"close": 1.0}
    with open(bundle_path, "w") as f:
        json.dump(payload, f)

    analyst.reset_report_store(base_dir=store.base_dir)   # drop the in-memory cache
    assert analyst.get_analyst_report(view.report_id).evidence_integrity_verified is False


def test_unknown_report_id_fails_closed():
    with pytest.raises(analyst.ResearchAnalystError, match="FAIL CLOSED"):
        analyst.get_analyst_report("report_does_not_exist")


def test_regenerating_produces_a_second_report_sharing_one_evidence_hash(as_of):
    a = _generate(as_of)
    b = _generate(as_of)
    assert a.report_id != b.report_id
    assert a.evidence_bundle_hash == b.evidence_bundle_hash
    assert len(analyst.list_analyst_reports()) == 2


def test_generation_can_skip_persistence(as_of):
    view = _generate(as_of, persist=False)
    assert view.report_id
    assert analyst.list_analyst_reports() == []
