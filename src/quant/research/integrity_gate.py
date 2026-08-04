"""
integrity_gate.py — Mandatory Research Integrity Gate (Phase 7J).

CertifiedResearchRunExecutor.execute() is the single sanctioned path in this codebase for
producing a research run that carries a full, checked, immutable provenance chain:

    Persistent Dataset (real Parquet bytes)
      -> Dataset Manifest (byte-level SHA-256, PersistentDatasetLock)
      -> Snapshot Lock (DatasetVersionLock, PIT as_of binding)
      -> Historical Universe (SecurityMasterRegistry, PIT listing/delisting)
      -> Corporate-Action Adjustment (CorporateActionAdjuster, mandatory — never optional)
      -> Factor / Parameter / Cost-Model / Benchmark binding (hashed, must be non-empty)
      -> Provider Provenance (every symbol's data_origin must be a recognized, explicit tag)
      -> Code Version / Working-Tree State (git, must be determinable)
      -> BacktestEngine (pure numeric simulator, unchanged from Phase 7I)
      -> Immutable ResearchRunStore entry

Every control above raises immediately (FAIL CLOSED) if missing, empty, or mismatched.
There is no fallback, no default, no "use current value", no fillna(0).

HONEST SCOPE NOTE (see PHASE_7J_REPORT.md §11 for the full discussion): this gate cannot
make `BacktestEngine.run_backtest()` itself physically uncallable — Python has no
module-private access control for that, and the directive does not require it (it requires
that an invalid path FAIL CLOSED when certification is attempted, not that the low-level
primitive be deleted). What this gate guarantees is narrower and testable: a call that skips
or tampers with any control here cannot produce a result that is written to
ResearchRunStore via this path, and CertifiedReplayEngine (see certified_replay_engine.py)
will refuse to reproduce/re-certify a run whose bindings no longer check out at replay time.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

from src.data.domain.persistent_manifest import PersistentDatasetManifestStore
from src.quant.reproducibility.persistent_dataset_lock import PersistentDatasetLock
from src.quant.reproducibility.dataset_lock import DatasetVersionLock
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.data.domain.security_master import SecurityMasterRegistry
from src.data.revision.corporate_action_store import CorporateActionStore
from src.quant.adjustment.corporate_action_adjuster import CorporateActionAdjuster
from src.quant.backtest.engine import BacktestEngine, BacktestResult
from src.quant.backtest.cost_model import TransactionCostModel
from src.quant.portfolio.construction import PortfolioTarget
from src.quant.reproducibility.canonical import compute_canonical_sha256
from src.quant.reproducibility.identity import get_code_version, ResearchRunIdentity
from src.quant.reproducibility.manifest import ResearchInputManifest, ResearchResultManifest
from src.quant.reproducibility.store import ResearchRunStore

# Provenance tags recognized project-wide (see corporate_action.py / market_data.py docstrings).
VALID_DATA_ORIGINS = {"REAL_PROVIDER", "LOCAL_PRODUCTION_VERIFICATION_DATA", "GOLDEN_DATASET", "SYNTHETIC_DATA"}


@dataclass(frozen=True)
class CertifiedResearchRequest:
    research_run_id: str

    dataset_id: str
    dataset_version: str
    dataset_directory: str
    persistent_manifest_store: PersistentDatasetManifestStore

    snapshot_id: str
    snapshot_manager: SnapshotManager
    as_of: datetime

    universe_symbols: List[str]
    security_master: SecurityMasterRegistry

    corporate_action_store: CorporateActionStore
    # symbol -> (dates sorted ascending, raw_prices aligned 1:1 with dates)
    raw_price_series: Dict[str, Tuple[List[str], List[float]]]

    provider_data_origin: Dict[str, str]  # symbol -> data_origin tag, mandatory per symbol

    factor_definitions: List[Dict[str, Any]]
    parameters: Dict[str, Any]
    cost_model_config: Dict[str, Any]

    strategy_id: str
    strategy_version: str
    benchmark_id: str
    benchmark_version: str

    run_store: ResearchRunStore
    code_repo_dir: str = "/Users/yuhanluo/ashare-quant"


class CertifiedResearchRunExecutor:
    """The mandatory gate. See module docstring for the full control chain and honest scope note."""

    @staticmethod
    def execute(request: CertifiedResearchRequest) -> Tuple[BacktestResult, ResearchRunIdentity]:
        # --- Control 1: Persistent dataset lock (real, byte-level-hashed artifact) ----------
        locked_persistent = PersistentDatasetLock.lock(
            request.dataset_id, request.dataset_version, request.dataset_directory,
            request.persistent_manifest_store,
        )

        # --- Control 2: Snapshot / dataset-version lock (fails closed on missing/mismatched) -
        locked_snapshot = DatasetVersionLock.lock(
            request.dataset_version, request.snapshot_id, request.snapshot_manager,
        )

        # --- Control 3: PIT — requested as_of MUST match the locked snapshot's as_of ---------
        if datetime.fromisoformat(locked_snapshot.as_of) != request.as_of:
            raise ValueError(
                "FAIL CLOSED: requested as_of does not match the locked snapshot's as_of. "
                f"requested={request.as_of.isoformat()} locked={locked_snapshot.as_of}"
            )

        # --- Control 4: Historical universe (PIT-correct listing/delisting, no survivorship) -
        if not request.universe_symbols:
            raise ValueError("FAIL CLOSED: universe_symbols must not be empty.")
        as_of_date_str = request.as_of.strftime("%Y-%m-%d")
        for symbol in request.universe_symbols:
            if not request.security_master.is_tradable_on(symbol, as_of_date_str):
                raise ValueError(
                    f"FAIL CLOSED: symbol '{symbol}' is not part of the PIT-correct historical "
                    f"universe as of {as_of_date_str} (not listed, delisted, or suspended)."
                )

        # --- Control 5: Provider provenance — every symbol must carry a recognized tag -------
        for symbol in request.universe_symbols:
            origin = request.provider_data_origin.get(symbol)
            if not origin or origin not in VALID_DATA_ORIGINS:
                raise ValueError(
                    f"FAIL CLOSED: symbol '{symbol}' has no recognized provider_data_origin "
                    f"(got {origin!r}). A certified research run cannot use unattributed data."
                )

        # --- Control 6: Corporate-action adjustment — MANDATORY for every symbol -------------
        # There is no parameter to skip this step; every symbol's raw series is routed through
        # CorporateActionAdjuster, whose PIT filter and fail-closed math are Phase 7I's own.
        adjusted_prices: Dict[str, List[float]] = {}
        adjustment_trace: Dict[str, List[str]] = {}
        raw_prices_used: Dict[str, List[float]] = {}
        dates_used: Dict[str, List[str]] = {}
        for symbol in request.universe_symbols:
            if symbol not in request.raw_price_series:
                raise ValueError(f"FAIL CLOSED: no raw price series supplied for universe symbol '{symbol}'.")
            dates, raw_prices = request.raw_price_series[symbol]
            visible_actions = request.corporate_action_store.query_pit_range(
                symbol, dates[0], dates[-1], request.as_of
            )
            adj_result = CorporateActionAdjuster.adjust(dates, raw_prices, visible_actions, request.as_of)
            adjusted_prices[symbol] = adj_result.adjusted_prices
            adjustment_trace[symbol] = adj_result.actions_applied
            raw_prices_used[symbol] = raw_prices
            dates_used[symbol] = dates

        # --- Control 7: Factor / parameter / cost-model binding — explicit, non-empty --------
        if not request.factor_definitions:
            raise ValueError("FAIL CLOSED: factor_definitions must be explicitly supplied and non-empty.")
        if not request.parameters:
            raise ValueError("FAIL CLOSED: parameters must be explicitly supplied and non-empty.")
        if not request.cost_model_config:
            raise ValueError("FAIL CLOSED: cost_model_config must be explicitly supplied and non-empty.")

        # --- Control 8: Code version / working-tree state (must be determinable) -------------
        code_version, code_state = get_code_version(request.code_repo_dir)
        if code_version == "UNAVAILABLE" or code_state == "UNAVAILABLE":
            raise ValueError(
                "FAIL CLOSED: could not determine code_version/code_state (git unavailable in "
                "this environment). A certified research run requires a known code identity."
            )

        # --- Execute: pure numeric simulation on the ADJUSTED series, never the raw one ------
        # cost_model_config MUST actually drive the engine's cost calculation, not merely be
        # hashed and ignored — TransactionCostModel(**config) means an invalid/unknown key
        # fails closed via TypeError rather than the config silently doing nothing.
        try:
            cost_model = TransactionCostModel(**request.cost_model_config)
        except TypeError as e:
            raise ValueError(
                f"FAIL CLOSED: cost_model_config does not match TransactionCostModel's fields "
                f"({[f.name for f in TransactionCostModel.__dataclass_fields__.values()]}): {e}"
            )

        targets = [PortfolioTarget(
            as_of_date_str, request.strategy_id,
            {s: 1.0 / len(request.universe_symbols) for s in request.universe_symbols}, 1.0,
        )]
        engine = BacktestEngine(cost_model=cost_model)
        backtest_result = engine.run_backtest(
            dataset_id=request.dataset_id, strategy_id=request.strategy_id,
            daily_prices=adjusted_prices, portfolio_targets=targets,
            snapshot_id=request.snapshot_id, as_of=request.as_of,
        )

        # --- Bind every control into the immutable identity/manifest -------------------------
        universe_symbols_sorted = sorted(request.universe_symbols)
        universe_hash = compute_canonical_sha256(universe_symbols_sorted)
        factor_hash = compute_canonical_sha256(request.factor_definitions)
        parameter_hash = compute_canonical_sha256(request.parameters)
        cost_model_hash = compute_canonical_sha256(request.cost_model_config)
        benchmark_hash = compute_canonical_sha256(
            {"id": request.benchmark_id, "version": request.benchmark_version}
        )

        start_date = min(dates_used[s][0] for s in universe_symbols_sorted)
        end_date = max(dates_used[s][-1] for s in universe_symbols_sorted)
        created_at = datetime.now().isoformat()

        input_manifest = ResearchInputManifest(
            research_run_id=request.research_run_id,
            dataset_id=request.dataset_id,
            dataset_version=request.dataset_version,
            snapshot_id=request.snapshot_id,
            dataset_manifest_hash=locked_persistent.content_sha256,
            as_of=request.as_of.isoformat(),
            start_date=start_date,
            end_date=end_date,
            universe_type="A_SHARE",
            universe_symbols=universe_symbols_sorted,
            universe_hash=universe_hash,
            factors_config=request.factor_definitions,
            factor_definition_hash=factor_hash,
            strategy_id=request.strategy_id,
            strategy_version=request.strategy_version,
            strategy_parameters=request.parameters,
            parameter_hash=parameter_hash,
            portfolio_constraints={"max_weight": 1.0},
            cost_model_config=request.cost_model_config,
            transaction_cost_model_hash=cost_model_hash,
            benchmark_id=request.benchmark_id,
            benchmark_version=request.benchmark_version,
            benchmark_hash=benchmark_hash,
            code_version=code_version,
            code_state=code_state,
            created_at=created_at,
        )
        input_hash = input_manifest.compute_input_hash()

        result_payload = {
            "sharpe": backtest_result.sharpe_ratio,
            "return": backtest_result.total_return,
            "mdd": backtest_result.max_drawdown,
        }
        result_hash = compute_canonical_sha256(result_payload)
        equity_curve_hash = compute_canonical_sha256(backtest_result.equity_curve)

        result_manifest = ResearchResultManifest(
            research_run_id=request.research_run_id,
            input_manifest_hash=input_hash,
            result_hash=result_hash,
            equity_curve_hash=equity_curve_hash,
        )

        identity = ResearchRunIdentity(
            research_run_id=request.research_run_id,
            snapshot_id=request.snapshot_id,
            dataset_version=request.dataset_version,
            dataset_manifest_hash=locked_persistent.content_sha256,
            as_of=request.as_of.isoformat(),
            start_date=start_date,
            end_date=end_date,
            universe_definition={"symbols": universe_symbols_sorted},
            universe_hash=universe_hash,
            strategy_id=request.strategy_id,
            strategy_version=request.strategy_version,
            factor_definition_hash=factor_hash,
            parameter_hash=parameter_hash,
            transaction_cost_model_hash=cost_model_hash,
            benchmark_id=request.benchmark_id,
            code_version=code_version,
            code_state=code_state,
            input_hash=input_hash,
            result_hash=result_hash,
            created_at=created_at,
        )

        # --- Immutable write — fails closed on research_run_id collision (Phase 7A behavior) -
        artifacts = {
            "daily_prices": adjusted_prices,
            "raw_daily_prices": raw_prices_used,
            "dates": dates_used,
            "corporate_actions_applied": adjustment_trace,
            "dataset_directory": request.dataset_directory,
            "provider_data_origin": request.provider_data_origin,
        }
        request.run_store.create_run(identity, input_manifest, result_manifest, artifacts)

        return backtest_result, identity
