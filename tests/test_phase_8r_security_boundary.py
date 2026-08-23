"""
test_phase_8r_security_boundary.py — Phase 8R Security Tests (CEO directive
CEO-2026-08-03-PHASE-8R-IMPLEMENT §13, categories A-G).

A. UI Boundary            — UI does not directly import protected research internals.
B. Application Boundary   — all research execution goes through CertifiedResearchRunExecutor.
C. Dataset Provenance     — GOLDEN_DATASET can never be labeled REAL_PROVIDER.
D. Parameter Identity     — changing as_of/universe/factor config/signal config changes identity.
E. Replay                 — UI-initiated replay goes through CertifiedReplayEngine.
F. Fail Closed            — invalid dataset/snapshot/factor/universe/missing PIT data all fail.
G. Trading Boundary       — no broker/order/live-trading execution path anywhere in src/app/.
"""

import ast
import os
import shutil
from datetime import date, datetime
from unittest.mock import patch

import pytest

from src.app import research_application as app

UI_FILE = os.path.join(os.path.dirname(__file__), "..", "src", "app", "streamlit_app.py")
APP_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "app")

# The directive's exact forbidden-internals list (§3).
FORBIDDEN_UI_IMPORTS = {
    "src.quant.backtest.engine",
    "src.quant.factors.registry",
    "src.quant.portfolio.construction",
    "src.quant.factors.base",
    "src.quant.factors.normalization",
    "src.quant.factors.multi_factor",
    "src.quant.signals.engine",
    "src.quant.research.integrity_gate",
    "src.quant.reproducibility.replay_engine",
    "src.quant.reproducibility.certified_replay_engine",
    "src.quant.adjustment.corporate_action_adjuster",
    "src.quant.reproducibility.dataset_lock",
    "src.quant.reproducibility.persistent_dataset_lock",
}

FORBIDDEN_TRADING_TERMS = [
    "place_order", "submit_order", "execute_trade", "broker", "order_router",
    "connect_broker", "buy_order", "sell_order", "live_trading", "paper_trading",
    "auto_execute", "trading_api_key", "trading_credentials",
]


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


# =================================================================================================
# A. UI Boundary
# =================================================================================================

def _ui_ast():
    with open(UI_FILE, "r") as f:
        return ast.parse(f.read(), filename=UI_FILE)


def test_a_ui_file_only_imports_the_application_layer_and_stdlib_streamlit():
    tree = _ui_ast()

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            # Reconstruct the full dotted path: "from src.app import research_application"
            # records module="src.app", names=["research_application"] — the importable
            # symbol is "src.app.research_application", not "src.app".
            for alias in node.names:
                imported_modules.add(f"{node.module}.{alias.name}")
            imported_modules.add(node.module)

    forbidden_hit = imported_modules & FORBIDDEN_UI_IMPORTS
    assert not forbidden_hit, f"UI layer imports forbidden research internals: {forbidden_hit}"

    # The UI may import Application Layer modules and NOTHING else from this project. The set
    # grew from one to two when AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §9 / §11
    # step 6 added the analyst page, whose orchestration lives in its own Application Layer
    # module exactly as that section specifies. This is an allow-list of Application Layer
    # entry points, not a relaxation: the FORBIDDEN_UI_IMPORTS check above is unchanged, and
    # any module outside this set — including any research internal — still fails.
    ALLOWED_APPLICATION_LAYER_MODULES = {
        "src.app.research_application",
        "src.app.research_analyst_application",
    }
    project_imports = {m for m in imported_modules if m.startswith("src.") and m != "src.app"}
    assert project_imports <= ALLOWED_APPLICATION_LAYER_MODULES, (
        f"UI layer must import Application Layer modules only "
        f"({sorted(ALLOWED_APPLICATION_LAYER_MODULES)}) and nothing else from this project; "
        f"found: {project_imports}"
    )


def test_a_ui_file_never_constructs_a_certified_research_request_directly():
    """AST-based (not string-based) check: no CALL anywhere in the file invokes a Phase 8A
    internal by name. A prose mention in the module docstring (explaining the architecture) is
    not a functional bypass and must not fail this test — only an actual Call node would be."""
    tree = _ui_ast()
    forbidden_callables = {
        "CertifiedResearchRequest", "CertifiedResearchRunExecutor", "CertifiedReplayEngine",
        "BacktestEngine", "FactorRegistry", "PortfolioConstructor", "MultiFactorEngine",
        "SignalEngine", "CorporateActionAdjuster",
    }
    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called_names.add(func.id)
            elif isinstance(func, ast.Attribute):
                called_names.add(func.attr)
    hit = called_names & forbidden_callables
    assert not hit, f"UI layer directly calls a Phase 8A internal: {hit}"


# =================================================================================================
# B. Application Boundary
# =================================================================================================

def test_b_create_research_run_actually_calls_certified_research_run_executor():
    from src.quant.research.integrity_gate import CertifiedResearchRunExecutor
    with patch.object(
        CertifiedResearchRunExecutor, "execute", wraps=CertifiedResearchRunExecutor.execute
    ) as spy:
        app.create_research_run(_default_params())
        assert spy.called, "create_research_run must invoke CertifiedResearchRunExecutor.execute"


def test_b_create_research_run_cannot_produce_a_stored_run_if_executor_is_bypassed():
    """If CertifiedResearchRunExecutor.execute is made to raise, no run may appear in the store —
    proving the Application Layer has no code path that stores a result without it."""
    from src.quant.research.integrity_gate import CertifiedResearchRunExecutor
    with patch.object(CertifiedResearchRunExecutor, "execute", side_effect=RuntimeError("boom")):
        with pytest.raises(app.ResearchRunError):
            app.create_research_run(_default_params(run_id="run_should_not_exist"))
    ctx = app.get_workbench_context()
    assert ctx.run_store.get_run("run_should_not_exist") is None


# =================================================================================================
# C. Dataset Provenance
# =================================================================================================

def test_c_golden_dataset_data_origin_is_hardcoded_not_a_parameter():
    import inspect
    sig = inspect.signature(app.ResearchRunParams)
    assert "data_origin" not in sig.parameters, (
        "ResearchRunParams must not expose a data_origin field — provenance is fixed, not user input"
    )


def test_c_created_run_provenance_is_always_golden_dataset():
    detail = app.create_research_run(_default_params())
    assert set(detail.provider_data_origin.values()) == {"GOLDEN_DATASET"}
    assert "REAL_PROVIDER" not in detail.provider_data_origin.values()


def test_c_golden_dataset_seed_module_never_tags_real_provider():
    from src.app import golden_dataset_seed as seed
    assert seed.DATA_ORIGIN == "GOLDEN_DATASET"
    for contract in seed._market_contracts():
        assert contract.data_origin == "GOLDEN_DATASET"
    for records in seed.fundamental_data().values():
        for record in records:
            assert record.data_origin == "GOLDEN_DATASET"
    assert seed.DEMO_DIVIDEND.data_origin == "GOLDEN_DATASET"


# =================================================================================================
# D. Parameter Identity
# =================================================================================================

def test_d_changing_factor_configuration_changes_identity_hash():
    a = app.create_research_run(_default_params(factor_ids=["momentum_20d:v1"], run_id="run_d_factor_a"))
    b = app.create_research_run(_default_params(factor_ids=["value_pe:v1"], run_id="run_d_factor_b"))
    assert a.factor_definition_hash != b.factor_definition_hash
    assert a.signal_configuration_hash != b.signal_configuration_hash


def test_d_changing_universe_changes_result():
    as_of_range = app.get_available_as_of_range()
    max_as_of = date.fromisoformat(as_of_range["max_as_of"])
    universe = app.get_universe(max_as_of)
    all_symbols = [s.symbol for s in universe.symbols]

    full = app.create_research_run(_default_params(universe_symbols=all_symbols, run_id="run_d_uni_full"))
    subset = app.create_research_run(
        _default_params(universe_symbols=all_symbols[:3], top_n=1, run_id="run_d_uni_subset")
    )
    assert full.universe_symbols != subset.universe_symbols


def test_d_changing_as_of_changes_snapshot_id():
    as_of_range = app.get_available_as_of_range()
    early = date.fromisoformat(as_of_range["min_as_of"])
    late = date.fromisoformat(as_of_range["max_as_of"])

    run_early = app.create_research_run(_default_params(as_of=early, top_n=1, run_id="run_d_as_of_early"))
    run_late = app.create_research_run(_default_params(as_of=late, run_id="run_d_as_of_late"))
    assert run_early.snapshot_id != run_late.snapshot_id
    assert run_early.as_of != run_late.as_of


# =================================================================================================
# E. Replay
# =================================================================================================

def test_e_replay_research_run_actually_calls_certified_replay_engine():
    from src.quant.reproducibility.certified_replay_engine import CertifiedReplayEngine
    created = app.create_research_run(_default_params())
    with patch.object(CertifiedReplayEngine, "replay", wraps=CertifiedReplayEngine.replay, autospec=True) as spy:
        app.replay_research_run(created.run_id)
        assert spy.called, "replay_research_run must invoke CertifiedReplayEngine.replay"


def test_e_replay_never_reimplements_its_own_reproducibility_check():
    """Static check: the Application Layer's replay function contains no independent hash
    comparison logic of its own — it only reformats what CertifiedReplayEngine already returned."""
    import inspect
    source = inspect.getsource(app.replay_research_run)
    assert "compute_canonical_sha256" not in source
    assert "==" not in source.split("try:")[0]  # no comparison logic before delegating to replay()


# =================================================================================================
# F. Fail Closed
# =================================================================================================

def test_f_invalid_factor_fails_closed_not_fallback():
    with pytest.raises(Exception):
        from src.quant.factors.registry import FactorSpec, FactorRegistry
        FactorRegistry.resolve(FactorSpec("not_a_real_factor:v1", {}))


def test_f_missing_pit_fundamental_data_fails_closed_end_to_end():
    """A universe requiring value_pe:v1 but with fundamental data stripped from the context
    must fail closed, not silently fall back to a default valuation."""
    ctx = app.get_workbench_context()
    ctx.fundamental_data.clear()
    with pytest.raises(app.ResearchRunError, match="FAIL CLOSED"):
        app.create_research_run(_default_params(factor_ids=["value_pe:v1"], top_n=1))


def test_f_tampered_dataset_bytes_fail_closed_through_the_application_layer():
    """Corrupting the certified dataset's on-disk bytes must be caught by the Application
    Layer's call into CertifiedResearchRunExecutor — not silently ignored."""
    ctx = app.get_workbench_context()
    parquet_files = [f for f in os.listdir(ctx.dataset_directory) if f.endswith(".parquet")]
    assert parquet_files
    target = os.path.join(ctx.dataset_directory, parquet_files[0])
    with open(target, "wb") as f:
        f.write(b"CORRUPTED NOT A REAL PARQUET FILE")

    with pytest.raises(app.ResearchRunError):
        app.create_research_run(_default_params(run_id="run_f_tampered"))


def test_f_invalid_universe_symbol_fails_closed():
    with pytest.raises(app.ResearchRunError, match="FAIL CLOSED"):
        app.create_research_run(_default_params(universe_symbols=["FAKE_SYMBOL.XX"]))


# =================================================================================================
# G. Trading Boundary
# =================================================================================================

def _code_identifiers(tree: ast.AST) -> set:
    """Collects identifiers that are actually part of executable code (function/class names,
    call targets, imported names, assignment targets) — deliberately excludes string literals,
    so prose in docstrings/comments/disclaimers (e.g. "No broker connection...") cannot trip
    this check merely by describing what the tool does NOT do."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def test_g_no_trading_shaped_code_constructs_anywhere_in_the_ui_layer():
    """Checks actual code identifiers (function/class defs, calls, imports, attribute access),
    never string literals — so the UI's own disclaimer text ('No broker connection, no order
    execution...') correctly does NOT trip this check, while a real `def place_order(...)` or
    `import broker_sdk` would."""
    for fname in os.listdir(APP_DIR):
        if not fname.endswith(".py"):
            continue
        with open(os.path.join(APP_DIR, fname), "r") as f:
            tree = ast.parse(f.read(), filename=fname)
        identifiers = {n.lower() for n in _code_identifiers(tree)}
        for term in FORBIDDEN_TRADING_TERMS:
            term_normalized = term.replace("_", "")
            hits = {n for n in identifiers if term_normalized in n.replace("_", "")}
            assert not hits, f"forbidden trading-shaped identifier(s) {hits} (matching '{term}') found in {fname}"


def test_g_application_layer_public_function_names_contain_no_trading_verbs():
    public_functions = [name for name in dir(app) if not name.startswith("_") and callable(getattr(app, name))]
    forbidden_verb_fragments = ["order", "trade", "broker", "execute_buy", "execute_sell", "place_"]
    for name in public_functions:
        lower = name.lower()
        for frag in forbidden_verb_fragments:
            assert frag not in lower, f"Application Layer function '{name}' contains forbidden fragment '{frag}'"


def test_g_no_broker_credential_fields_anywhere_in_view_models():
    import inspect
    for name, obj in vars(app).items():
        if inspect.isclass(obj) and hasattr(obj, "__dataclass_fields__"):
            field_names = set(obj.__dataclass_fields__.keys())
            forbidden = {"broker_api_key", "trading_token", "order_id", "account_id", "broker_credentials"}
            assert not (field_names & forbidden), f"{name} exposes forbidden trading field(s)"
