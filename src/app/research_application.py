"""
research_application.py — Research Application Layer (Phase 8R).

The ONLY code the UI layer is permitted to import from this project. Plain Python, zero
UI-framework imports (no Streamlit/Flask/FastAPI here — see docs/PHASE_8R_ARCHITECTURE_
PROPOSAL.md §3/§7 for why this module must stay framework-agnostic).

Every function here does exactly one of: (a) read already-certified data and reformat it into
a UI-friendly view, or (b) translate UI-collected parameters into a CertifiedResearchRequest
and call CertifiedResearchRunExecutor.execute() / CertifiedReplayEngine.replay() — Phase 8A's
own, unmodified, adversarially-tested entry points. This module contains no factor math, no
normalization, no signal logic, no portfolio construction, and no backtest simulation of its
own — grep for BacktestEngine/FactorNormalizer/MultiFactorEngine/SignalEngine/
PortfolioConstructor/CorporateActionAdjuster call sites in this file: the only ones are inside
CertifiedResearchRunExecutor.execute() and CertifiedReplayEngine.replay(), which this module
calls, never reimplements.

NOTE on _WORKBENCH_METRICS_DIR: CertifiedResearchRunExecutor.execute() returns the numeric
BacktestResult (total_return, sharpe_ratio, etc.) to its immediate caller, but ResearchRunStore
only persists that result's HASH (result_hash), not the numbers themselves — Phase 8A never
needed to look up a past run's raw metrics again, only to verify its hash on replay. Phase 8R's
"view an old research run" requirement needs those numbers back later, in a fresh process. Since
touching integrity_gate.py to add a metrics artifact would be a Phase 8A modification (requires
its own directive per CEO instruction), this module instead writes a small, clearly Phase-8R-
owned side-cache (data/research/workbench_metrics/<run_id>.json, gitignored under the existing
data/research/ rule) at creation time, purely for display. It carries no certification weight —
Replay always independently recomputes and compares the real result_hash via Phase 8A's own
logic; this cache is read-only display convenience, never a comparison target.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from src.data.domain.persistent_manifest import PersistentDatasetManifestStore
from src.data.domain.security_master import SecurityMasterRegistry
from src.data.revision.corporate_action_store import CorporateActionStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.quant.reproducibility.store import ResearchRunStore
from src.quant.reproducibility.certified_replay_engine import (
    CertifiedReplayEngine, IntermediateArtifactMismatchError, ReplayStatus,
)
from src.quant.factors.registry import FactorRegistry, FactorSpec
from src.quant.factors.multi_factor import FactorWeightConfig
from src.quant.research.integrity_gate import CertifiedResearchRequest, CertifiedResearchRunExecutor

from src.app.golden_dataset_seed import (
    ensure_golden_dataset, build_security_master, build_corporate_action_store,
    fundamental_data as golden_fundamental_data, TRADING_DATE_STRS, PRICES_BY_SYMBOL,
    SYMBOL_DISPLAY_NAMES, DATA_ORIGIN as GOLDEN_DATA_ORIGIN,
)

RESEARCH_BASE_DIR = "data/research"
MANIFEST_BASE_DIR = "data/manifests"
RUN_STORE_BASE_DIR = "data/research/runs"
_WORKBENCH_METRICS_DIR = "data/research/workbench_metrics"

DEFAULT_STRATEGY_ID = "workbench_research"
DEFAULT_STRATEGY_VERSION = "1.0.0"
DEFAULT_BENCHMARK_ID = "000300.SH"
DEFAULT_BENCHMARK_VERSION = "1.0"

LIMITATIONS = [
    "Live provider verification is NOT VERIFIED — TUSHARE_TOKEN is unavailable in this "
    "environment; all data in this workbench is GOLDEN_DATASET, never REAL_PROVIDER.",
    "BacktestResult.turnover is a fixed placeholder (0.15), not derived from actual position "
    "changes (deferred, Phase 8A §16).",
    "BacktestResult.trade_count reflects the number of simulated days, not a real trade count "
    "(deferred, Phase 8A §16).",
    "TransactionCostModel charges a flat percentage of equity per day; it is not yet driven by "
    "actual portfolio turnover or trade direction (deferred, Phase 8A §16).",
    "Historical backtest results are research outputs and do not guarantee future performance.",
]


class ResearchRunError(Exception):
    """Wraps any error raised by the certified pipeline for UI display. Never swallows or
    falls back to a default — always re-raised with the original FAIL CLOSED message intact."""
    pass


# --- Workbench context: a process-lifetime singleton holding the in-memory stores that have --
# --- no disk persistence of their own (SecurityMasterRegistry, CorporateActionStore,          --
# --- SnapshotManager) plus the disk-backed ones (PersistentDatasetManifestStore, ResearchRunStore).

@dataclass
class WorkbenchContext:
    security_master: SecurityMasterRegistry
    corporate_action_store: CorporateActionStore
    persistent_manifest_store: PersistentDatasetManifestStore
    snapshot_manager: SnapshotManager
    run_store: ResearchRunStore
    fundamental_data: Dict[str, List[Any]]
    dataset_id: str
    dataset_version: str
    dataset_directory: str
    dataset_content_sha256: str
    universe_symbols: List[str]
    first_date: str
    last_date: str


_context: Optional[WorkbenchContext] = None


def get_workbench_context() -> WorkbenchContext:
    """Lazily builds (once per process) and returns the singleton workbench context. Idempotent
    — safe to call from every UI page load."""
    global _context
    if _context is not None:
        return _context

    golden = ensure_golden_dataset(RESEARCH_BASE_DIR, MANIFEST_BASE_DIR)
    _context = WorkbenchContext(
        security_master=build_security_master(),
        corporate_action_store=build_corporate_action_store(),
        persistent_manifest_store=PersistentDatasetManifestStore(base_dir=MANIFEST_BASE_DIR),
        snapshot_manager=SnapshotManager(),
        run_store=ResearchRunStore(base_dir=RUN_STORE_BASE_DIR),
        fundamental_data=golden_fundamental_data(),
        dataset_id=golden.dataset_id, dataset_version=golden.dataset_version,
        dataset_directory=golden.directory, dataset_content_sha256=golden.manifest.content_sha256,
        universe_symbols=golden.symbols, first_date=golden.first_date, last_date=golden.last_date,
    )
    return _context


def reset_workbench_context() -> None:
    """Test-only escape hatch to force a fresh context (e.g. between isolated test cases)."""
    global _context
    _context = None


# --- View models -----------------------------------------------------------------------------

@dataclass(frozen=True)
class DatasetView:
    dataset_id: str
    dataset_version: str
    directory: str
    content_sha256: str
    data_origin: str
    symbols: List[str]
    first_date: str
    last_date: str


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    display_name: str
    tradable_as_of: bool


@dataclass(frozen=True)
class UniverseView:
    as_of: str
    symbols: List[SymbolInfo]
    note: str = (
        "This is the historical, point-in-time universe as of the selected date — not today's "
        "current listing. Delisted/suspended symbols as of this date are marked not tradable "
        "and excluded from research runs, preventing survivorship bias."
    )


@dataclass(frozen=True)
class FactorDefinitionView:
    factor_id: str
    data_source: str
    direction: str
    description: str


@dataclass(frozen=True)
class ResearchRunParams:
    as_of: date
    universe_symbols: List[str]
    factor_ids: List[str]              # subset of {"momentum_20d:v1", "value_pe:v1"}
    top_n: int
    commission_rate: float = 0.0003
    min_cross_sectional_samples: int = 3
    run_id: Optional[str] = None       # auto-generated if omitted


@dataclass(frozen=True)
class ResearchRunSummaryView:
    run_id: str
    dataset_id: str
    dataset_version: str
    snapshot_id: str
    as_of: str
    factor_ids: List[str]
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    created_at: str


@dataclass(frozen=True)
class ResearchRunDetailView:
    run_id: str
    dataset_id: str
    dataset_version: str
    dataset_sha256: str
    snapshot_id: str
    as_of: str
    universe_symbols: List[str]
    factor_definitions: List[Dict[str, Any]]
    factor_definition_hash: str
    signal_config: List[Dict[str, Any]]
    signal_configuration_hash: str
    portfolio_weights: Dict[str, float]
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    provider_data_origin: Dict[str, str]
    code_version: str
    code_state: str
    result_hash: str
    certification_status: str          # "CERTIFIED" — always, since it can only exist via the gate
    limitations: List[str]
    created_at: str
    corporate_actions_applied: Dict[str, List[str]]


@dataclass(frozen=True)
class ReplayView:
    run_id: str
    status: str   # "REPRODUCIBLE" | "INTERMEDIATE_ARTIFACT_MISMATCH" | "FINAL_RESULT_MISMATCH" | "ERROR"
    original_result_hash: Optional[str]
    replayed_result_hash: Optional[str]
    explanation: str


@dataclass(frozen=True)
class IntegrityReportView:
    run_id: str
    dataset_hash_present: bool
    snapshot_id: str
    as_of: str
    pit_status: str
    corporate_actions_applied: Dict[str, List[str]]
    factor_definition_hash: str
    signal_configuration_hash: str
    provider_data_origin: Dict[str, str]
    live_provider_status: str = "NOT VERIFIED (TUSHARE_TOKEN unavailable)"


# --- 1/2/3/4: available dataset / snapshot(as_of) / universe / factor configurations ----------

def get_available_datasets() -> List[DatasetView]:
    ctx = get_workbench_context()
    return [DatasetView(
        dataset_id=ctx.dataset_id, dataset_version=ctx.dataset_version, directory=ctx.dataset_directory,
        content_sha256=ctx.dataset_content_sha256, data_origin=GOLDEN_DATA_ORIGIN,
        symbols=list(ctx.universe_symbols), first_date=ctx.first_date, last_date=ctx.last_date,
    )]


def get_available_as_of_range() -> Dict[str, str]:
    ctx = get_workbench_context()
    return {"min_as_of": ctx.first_date, "max_as_of": ctx.last_date}


def get_universe(as_of: date) -> UniverseView:
    ctx = get_workbench_context()
    as_of_str = as_of.strftime("%Y-%m-%d")
    symbols = [
        SymbolInfo(
            symbol=s, display_name=SYMBOL_DISPLAY_NAMES.get(s, s),
            tradable_as_of=ctx.security_master.is_tradable_on(s, as_of_str),
        )
        for s in ctx.universe_symbols
    ]
    return UniverseView(as_of=as_of_str, symbols=symbols)


_FACTOR_DESCRIPTIONS = {
    "momentum_20d:v1": "Price momentum over a trailing window (higher = preferred).",
    "value_pe:v1": "Valuation via trailing PE (lower = preferred); PIT-gated on fundamental provenance.",
}


def get_factor_definitions() -> List[FactorDefinitionView]:
    views = []
    for factor_id, (factory, data_source, direction) in sorted(FactorRegistry._entries.items()):
        views.append(FactorDefinitionView(
            factor_id=factor_id, data_source=data_source, direction=direction.value,
            description=_FACTOR_DESCRIPTIONS.get(factor_id, ""),
        ))
    return views


# --- 5/6: build + validate the certified request, execute it ----------------------------------

def _ensure_snapshot(ctx: WorkbenchContext, as_of: datetime) -> str:
    """Deterministically derives a snapshot_id from (dataset_version, as_of) and registers it
    if not already present. This is snapshot *selection* from the UI's point of view (directive
    §4 item 2) — the underlying SnapshotManager object is unchanged Phase 7A/7J code."""
    snapshot_id = f"snap_{ctx.dataset_version}_{as_of.strftime('%Y%m%d')}"
    if ctx.snapshot_manager.get_snapshot(snapshot_id) is None:
        ctx.snapshot_manager.create_snapshot(
            as_of=as_of, dataset_version=ctx.dataset_version, snapshot_id=snapshot_id
        )
    return snapshot_id


def _build_signal_config(factor_ids: List[str]) -> List[FactorWeightConfig]:
    """Equal-weights whichever factors the user selected, using each factor's REGISTERED
    direction (never a UI-chosen direction) so a caller can never silently contradict what
    FactorRegistry actually says a factor means."""
    if not factor_ids:
        raise ResearchRunError("FAIL CLOSED: at least one factor must be selected.")
    weight = round(1.0 / len(factor_ids), 6)
    configs = []
    for factor_id in factor_ids:
        _, definition = FactorRegistry.resolve(FactorSpec(factor_id, {}))
        configs.append(FactorWeightConfig(factor_id, weight, definition.direction))
    return configs


def create_research_run(params: ResearchRunParams) -> ResearchRunDetailView:
    """The one function in this codebase where user input becomes a certified research run.
    Translates ResearchRunParams into a CertifiedResearchRequest and calls
    CertifiedResearchRunExecutor.execute() — never computes a result itself."""
    ctx = get_workbench_context()

    if not params.universe_symbols:
        raise ResearchRunError("FAIL CLOSED: universe_symbols must not be empty.")
    unknown = set(params.universe_symbols) - set(ctx.universe_symbols)
    if unknown:
        raise ResearchRunError(f"FAIL CLOSED: unknown symbol(s) not in the certified dataset: {sorted(unknown)}")

    as_of_dt = datetime(params.as_of.year, params.as_of.month, params.as_of.day)
    snapshot_id = _ensure_snapshot(ctx, as_of_dt)

    factor_definitions = [FactorSpec(fid, {}) for fid in sorted(params.factor_ids)]
    signal_config = _build_signal_config(sorted(params.factor_ids))

    run_id = params.run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

    request = CertifiedResearchRequest(
        research_run_id=run_id,
        dataset_id=ctx.dataset_id, dataset_version=ctx.dataset_version,
        dataset_directory=ctx.dataset_directory, persistent_manifest_store=ctx.persistent_manifest_store,
        snapshot_id=snapshot_id, snapshot_manager=ctx.snapshot_manager, as_of=as_of_dt,
        universe_symbols=list(params.universe_symbols), security_master=ctx.security_master,
        corporate_action_store=ctx.corporate_action_store,
        raw_price_series={s: (TRADING_DATE_STRS, PRICES_BY_SYMBOL[s]) for s in params.universe_symbols},
        provider_data_origin={s: GOLDEN_DATA_ORIGIN for s in params.universe_symbols},
        factor_definitions=factor_definitions,
        fundamental_data=ctx.fundamental_data,
        signal_config=signal_config,
        parameters={"top_n": params.top_n},
        cost_model_config={"commission_rate": params.commission_rate},
        strategy_id=DEFAULT_STRATEGY_ID, strategy_version=DEFAULT_STRATEGY_VERSION,
        benchmark_id=DEFAULT_BENCHMARK_ID, benchmark_version=DEFAULT_BENCHMARK_VERSION,
        run_store=ctx.run_store, min_cross_sectional_samples=params.min_cross_sectional_samples,
    )

    try:
        result, identity = CertifiedResearchRunExecutor.execute(request)
    except Exception as e:
        raise ResearchRunError(str(e)) from e

    _save_metrics(run_id, result)
    return get_research_run(run_id)


def _save_metrics(run_id: str, result: Any) -> None:
    os.makedirs(_WORKBENCH_METRICS_DIR, exist_ok=True)
    path = os.path.join(_WORKBENCH_METRICS_DIR, f"{run_id}.json")
    with open(path, "w") as f:
        json.dump({
            "total_return": result.total_return,
            "annualized_return": result.annualized_return,
            "annualized_volatility": result.annualized_volatility,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
        }, f)


def _load_metrics(run_id: str) -> Dict[str, float]:
    path = os.path.join(_WORKBENCH_METRICS_DIR, f"{run_id}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


# --- 7/9: query a research run + its result ----------------------------------------------------

def get_research_run(run_id: str) -> ResearchRunDetailView:
    ctx = get_workbench_context()
    run_data = ctx.run_store.get_run(run_id)
    if not run_data:
        raise ResearchRunError(f"FAIL CLOSED: Research Run '{run_id}' not found.")

    identity = run_data["identity"]
    input_manifest = run_data["input_manifest"]
    result_manifest = run_data["result_manifest"]
    artifacts = run_data.get("artifacts", {})

    # Display metrics come from the Phase-8R-owned side cache (see module docstring) — the
    # certification-relevant fields below (hashes, identity, universe, factor config, weights)
    # all come directly from Phase 8A's own stored identity/input_manifest/artifacts.
    metrics = _load_metrics(run_id)

    return ResearchRunDetailView(
        run_id=run_id, dataset_id=input_manifest.dataset_id, dataset_version=input_manifest.dataset_version,
        dataset_sha256=input_manifest.dataset_manifest_hash, snapshot_id=input_manifest.snapshot_id,
        as_of=input_manifest.as_of, universe_symbols=input_manifest.universe_symbols,
        factor_definitions=input_manifest.factors_config, factor_definition_hash=input_manifest.factor_definition_hash,
        signal_config=input_manifest.signal_config, signal_configuration_hash=input_manifest.signal_configuration_hash,
        portfolio_weights=artifacts.get("portfolio_weights", {}),
        total_return=float(metrics.get("total_return", 0.0)),
        annualized_return=float(metrics.get("annualized_return", 0.0)),
        annualized_volatility=float(metrics.get("annualized_volatility", 0.0)),
        sharpe_ratio=float(metrics.get("sharpe_ratio", 0.0)),
        max_drawdown=float(metrics.get("max_drawdown", 0.0)),
        win_rate=float(metrics.get("win_rate", 0.0)),
        provider_data_origin=artifacts.get("provider_data_origin", {}),
        code_version=identity.code_version, code_state=identity.code_state,
        result_hash=identity.result_hash, certification_status="CERTIFIED",
        limitations=list(LIMITATIONS), created_at=input_manifest.created_at,
        corporate_actions_applied=artifacts.get("corporate_actions_applied", {}),
    )


def list_research_runs() -> List[ResearchRunSummaryView]:
    ctx = get_workbench_context()
    summaries = []
    for run_id in ctx.run_store.list_runs():
        try:
            detail = get_research_run(run_id)
        except ResearchRunError:
            continue
        summaries.append(ResearchRunSummaryView(
            run_id=detail.run_id, dataset_id=detail.dataset_id, dataset_version=detail.dataset_version,
            snapshot_id=detail.snapshot_id, as_of=detail.as_of,
            factor_ids=[f["factor_id"] for f in detail.factor_definitions],
            total_return=detail.total_return, sharpe_ratio=detail.sharpe_ratio,
            max_drawdown=detail.max_drawdown, created_at=detail.created_at,
        ))
    return summaries


# --- 8: replay ----------------------------------------------------------------------------------

def replay_research_run(run_id: str) -> ReplayView:
    ctx = get_workbench_context()
    replay_engine = CertifiedReplayEngine(
        ctx.run_store, ctx.snapshot_manager, ctx.persistent_manifest_store,
        ctx.corporate_action_store, ctx.security_master, ctx.fundamental_data,
    )
    try:
        report = replay_engine.replay(run_id)
    except IntermediateArtifactMismatchError as e:
        return ReplayView(
            run_id=run_id, status="INTERMEDIATE_ARTIFACT_MISMATCH",
            original_result_hash=None, replayed_result_hash=None, explanation=str(e),
        )
    except Exception as e:
        return ReplayView(
            run_id=run_id, status="ERROR",
            original_result_hash=None, replayed_result_hash=None, explanation=str(e),
        )

    return ReplayView(
        run_id=run_id, status=report.status.value,
        original_result_hash=report.original_result_hash, replayed_result_hash=report.replayed_result_hash,
        explanation=report.explanation,
    )


# --- 10: provenance / certification metadata -----------------------------------------------------

def get_integrity_report(run_id: str) -> IntegrityReportView:
    detail = get_research_run(run_id)
    return IntegrityReportView(
        run_id=run_id, dataset_hash_present=bool(detail.dataset_sha256),
        snapshot_id=detail.snapshot_id, as_of=detail.as_of,
        pit_status="ENFORCED (available_at/received_at <= as_of, verified by Phase 8A)",
        corporate_actions_applied=detail.corporate_actions_applied,
        factor_definition_hash=detail.factor_definition_hash,
        signal_configuration_hash=detail.signal_configuration_hash,
        provider_data_origin=detail.provider_data_origin,
    )


# --- Research Report export --------------------------------------------------------------------

def generate_research_report(run_id: str) -> str:
    """Renders a Markdown research report from already-certified, already-stored data. Calls
    replay_research_run() to include a live integrity check, but performs no factor/signal/
    portfolio/backtest computation of its own."""
    detail = get_research_run(run_id)
    replay = replay_research_run(run_id)

    factor_lines = "\n".join(
        f"- `{f['factor_id']}`  parameters={f['parameters']}" for f in detail.factor_definitions
    )
    signal_lines = "\n".join(
        f"- `{c['factor_name']}`  weight={c['weight']}  direction={c['direction']}"
        for c in detail.signal_config
    )
    weight_lines = "\n".join(
        f"- `{sym}`: {w:.4f}" for sym, w in sorted(detail.portfolio_weights.items())
    ) or "_(fully cash — no positions selected)_"
    provenance_lines = "\n".join(
        f"- `{sym}`: {origin}" for sym, origin in sorted(detail.provider_data_origin.items())
    )
    corp_action_lines = "\n".join(
        f"- `{sym}`: {actions if actions else '(none applied)'}"
        for sym, actions in sorted(detail.corporate_actions_applied.items())
    ) or "_(no corporate actions in this run's universe/window)_"
    limitations_lines = "\n".join(f"- {item}" for item in detail.limitations)

    return f"""# Research Report — {detail.run_id}

**Generated from a Phase 8A CertifiedResearchRunExecutor run. Historical backtest results are
research outputs and do not guarantee future performance.**

## 1. Executive Summary

| Field | Value |
|---|---|
| Research Run ID | `{detail.run_id}` |
| As-of Date | {detail.as_of} |
| Universe | {", ".join(detail.universe_symbols)} |
| Factors | {", ".join(f["factor_id"] for f in detail.factor_definitions)} |
| Total Return | {detail.total_return:.4%} |
| Annualized Return | {detail.annualized_return:.4%} |
| Sharpe Ratio | {detail.sharpe_ratio:.4f} |
| Max Drawdown | {detail.max_drawdown:.4%} |
| Certification Status | {detail.certification_status} |
| Replay Status | {replay.status} |

## 2. Factor Analysis

**Factor definitions (bound into `factor_definition_hash={detail.factor_definition_hash[:16]}...`):**
{factor_lines}

**Signal configuration (bound into `signal_configuration_hash={detail.signal_configuration_hash[:16]}...`):**
{signal_lines}

## 3. Portfolio

**Research Portfolio / Historical Target Weights** (NOT a live or trading portfolio):
{weight_lines}

## 4. Backtest

| Metric | Value |
|---|---|
| Total Return | {detail.total_return:.4%} |
| Annualized Return | {detail.annualized_return:.4%} |
| Annualized Volatility | {detail.annualized_volatility:.4%} |
| Sharpe Ratio | {detail.sharpe_ratio:.4f} |
| Max Drawdown | {detail.max_drawdown:.4%} |
| Win Rate | {detail.win_rate:.4%} |

## 5. Integrity

| Check | Value |
|---|---|
| Dataset ID / Version | `{detail.dataset_id}` / `{detail.dataset_version}` |
| Dataset SHA-256 | `{detail.dataset_sha256}` |
| Snapshot ID | `{detail.snapshot_id}` |
| Code Version | `{detail.code_version}` ({detail.code_state}) |
| Result Hash | `{detail.result_hash}` |
| Replay Status | **{replay.status}** — {replay.explanation} |

**Provider provenance** (never REAL_PROVIDER in this environment — TUSHARE_TOKEN unavailable):
{provenance_lines}

**Corporate actions applied (PIT-filtered):**
{corp_action_lines}

## 6. Limitations

{limitations_lines}

---
*Historical backtest results are research outputs and do not guarantee future performance.
This is a Research & Backtest analysis output only — not a live or trading portfolio, not investment advice, and not an automatic trading signal.*
"""
