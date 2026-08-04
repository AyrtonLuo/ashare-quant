"""
integrity_gate.py — Mandatory Research Integrity Gate (Phase 7J + Phase 8A Factor Engine).

CertifiedResearchRunExecutor.execute() is the single sanctioned path in this codebase for
producing a research run that carries a full, checked, immutable provenance chain:

    Persistent Dataset (real Parquet bytes)
      -> Dataset Manifest (byte-level SHA-256, PersistentDatasetLock)
      -> Snapshot Lock (DatasetVersionLock, PIT as_of binding)
      -> Historical Universe (SecurityMasterRegistry, PIT listing/delisting)
      -> Corporate-Action Adjustment (CorporateActionAdjuster, mandatory — never optional)
      -> Provider Provenance (every symbol's data_origin must be a recognized, explicit tag)
      -> Factor Resolution (FactorRegistry — factor_definitions is MANDATORY, no fallback)
      -> Factor Calculation (per symbol, PIT-filtered; market-data or fundamental-data sourced)
      -> Cross-sectional Normalization (locked universe, minimum sample size enforced)
      -> Composite Signal (MultiFactorEngine + SignalEngine)
      -> Portfolio Construction (GenericFactorStrategy -> PortfolioConstructor)
      -> Parameter / Cost-Model / Benchmark binding (hashed, must be non-empty)
      -> Code Version / Working-Tree State (git, must be determinable)
      -> BacktestEngine (Phase 8A hardened: genuinely consumes portfolio weights)
      -> Immutable ResearchRunStore entry

Every control above raises immediately (FAIL CLOSED) if missing, empty, unknown, or
mismatched. There is no fallback, no default, no "use current value", no fillna(0), and
— as of Phase 8A — no hard-coded equal-weight portfolio construction inside this executor.

HONEST SCOPE NOTE (see PHASE_7J_REPORT.md §11 / PHASE_8A_REPORT.md for the full discussion):
this gate cannot make `BacktestEngine.run_backtest()` itself physically uncallable — Python
has no module-private access control for that. What this gate guarantees is narrower and
testable: a call that skips or tampers with any control here cannot produce a result that is
written to ResearchRunStore via this path, and CertifiedReplayEngine will refuse to
reproduce/re-certify a run whose bindings — now including the full factor/signal/portfolio
chain — no longer check out at replay time.
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
from src.quant.portfolio.construction import PortfolioConstructor
from src.quant.reproducibility.canonical import compute_canonical_sha256
from src.quant.reproducibility.identity import get_code_version, ResearchRunIdentity
from src.quant.reproducibility.manifest import ResearchInputManifest, ResearchResultManifest
from src.quant.reproducibility.store import ResearchRunStore
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.validation.pit_gate import PITGate
from src.quant.factors.registry import FactorRegistry, FactorSpec, DATA_SOURCE_MARKET, DATA_SOURCE_FUNDAMENTAL
from src.quant.factors.base import FactorValue, FactorStatus
from src.quant.factors.normalization import FactorNormalizer
from src.quant.factors.multi_factor import MultiFactorEngine, FactorWeightConfig
from src.quant.signals.engine import SignalEngine
from src.quant.strategies.generic_factor_strategy import GenericFactorStrategy

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

    # Phase 8A — MANDATORY, no fallback (CEO directive 008A-IMPLEMENT §2, DECISION 1).
    factor_definitions: List[FactorSpec]
    fundamental_data: Dict[str, List[FundamentalDataContract]]  # symbol -> ALL known revisions
    signal_config: List[FactorWeightConfig]  # how factors combine into one composite signal

    parameters: Dict[str, Any]          # must include an explicit int "top_n"
    cost_model_config: Dict[str, Any]

    strategy_id: str
    strategy_version: str
    benchmark_id: str
    benchmark_version: str

    run_store: ResearchRunStore
    min_cross_sectional_samples: int = 3
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
        universe_symbols_sorted = sorted(request.universe_symbols)
        for symbol in universe_symbols_sorted:
            if not request.security_master.is_tradable_on(symbol, as_of_date_str):
                raise ValueError(
                    f"FAIL CLOSED: symbol '{symbol}' is not part of the PIT-correct historical "
                    f"universe as of {as_of_date_str} (not listed, delisted, or suspended)."
                )

        # --- Control 5: Provider provenance — every symbol must carry a recognized tag -------
        for symbol in universe_symbols_sorted:
            origin = request.provider_data_origin.get(symbol)
            if not origin or origin not in VALID_DATA_ORIGINS:
                raise ValueError(
                    f"FAIL CLOSED: symbol '{symbol}' has no recognized provider_data_origin "
                    f"(got {origin!r}). A certified research run cannot use unattributed data."
                )

        # --- Control 6: Corporate-action adjustment — MANDATORY for every symbol -------------
        adjusted_prices: Dict[str, List[float]] = {}
        adjustment_trace: Dict[str, List[str]] = {}
        raw_prices_used: Dict[str, List[float]] = {}
        dates_used: Dict[str, List[str]] = {}
        for symbol in universe_symbols_sorted:
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

        # --- Control 7: Factor resolution — MANDATORY, FAIL CLOSED on empty/unknown/invalid --
        # No None/empty fallback, no hidden default factor, no hard-coded factor result.
        # factor_definitions is sorted by factor_id before resolution/hashing so caller list
        # order can never change the resulting factor_definition_hash.
        sorted_specs = sorted(request.factor_definitions, key=lambda s: s.factor_id)
        resolved_factors = FactorRegistry.resolve_all(sorted_specs)  # raises FAIL CLOSED internally
        resolved_factor_ids = [d.factor_id for _, d in resolved_factors]
        resolved_direction_by_id = {d.factor_id: d.direction for _, d in resolved_factors}

        # --- Control 8: signal_config — MANDATORY, must exactly match the resolved factors ---
        if not request.signal_config:
            raise ValueError("FAIL CLOSED: signal_config must be explicitly supplied and non-empty.")
        sorted_signal_config = sorted(request.signal_config, key=lambda c: c.factor_name)
        signal_factor_names = {cfg.factor_name for cfg in sorted_signal_config}
        if signal_factor_names != set(resolved_factor_ids):
            raise ValueError(
                f"FAIL CLOSED: signal_config factor_name set {sorted(signal_factor_names)} does "
                f"not match resolved factor_definitions {sorted(resolved_factor_ids)}."
            )
        for cfg in sorted_signal_config:
            if cfg.direction != resolved_direction_by_id[cfg.factor_name]:
                raise ValueError(
                    f"FAIL CLOSED: signal_config direction for '{cfg.factor_name}' "
                    f"({cfg.direction}) does not match the FactorRegistry's registered "
                    f"direction ({resolved_direction_by_id[cfg.factor_name]}). A caller cannot "
                    "silently override a factor's registered semantics via signal_config."
                )

        # --- Control 9: cross-sectional sample threshold must be explicit and sane -----------
        if request.min_cross_sectional_samples < 1:
            raise ValueError("FAIL CLOSED: min_cross_sectional_samples must be >= 1.")

        # --- Control 10: per-factor, per-symbol calculation (PIT-filtered) --------------------
        factor_matrices: Dict[str, Dict[str, float]] = {}
        factor_value_trace: Dict[str, Dict[str, Any]] = {}
        for factor_instance, factor_def in resolved_factors:
            values: List[FactorValue] = []
            if factor_def.data_source == DATA_SOURCE_MARKET:
                for symbol in universe_symbols_sorted:
                    values.append(
                        factor_instance.compute(symbol, adjusted_prices[symbol], as_of_date_str, request.as_of)
                    )
            elif factor_def.data_source == DATA_SOURCE_FUNDAMENTAL:
                for symbol in universe_symbols_sorted:
                    records = request.fundamental_data.get(symbol, [])
                    pit_visible = PITGate.filter_pit_fundamentals(records, request.as_of)
                    if not pit_visible:
                        values.append(FactorValue(
                            symbol=symbol, factor_name=factor_def.factor_id, factor_version="n/a",
                            raw_value=None, effective_date=as_of_date_str, as_of=request.as_of,
                            status=FactorStatus.NOT_APPLICABLE,
                            quality_notes="no PIT-visible fundamental record (available_at/received_at <= as_of)",
                        ))
                        continue
                    selected = max(pit_visible, key=lambda r: (r.report_date, r.available_at))
                    metric_type = getattr(factor_instance, "metric_type", None)
                    val = getattr(selected, metric_type, None) if metric_type else None
                    values.append(
                        factor_instance.compute_from_fundamental(
                            symbol, val, selected.provenance, as_of_date_str, request.as_of
                        )
                    )
            else:
                raise ValueError(
                    f"FAIL CLOSED: unhandled data_source '{factor_def.data_source}' for "
                    f"factor '{factor_def.factor_id}'."
                )

            valid_count = sum(1 for v in values if v.status == FactorStatus.VALID)
            if valid_count < request.min_cross_sectional_samples:
                raise ValueError(
                    f"FAIL CLOSED: factor '{factor_def.factor_id}' produced only {valid_count} "
                    f"valid cross-sectional value(s) across the locked universe (minimum "
                    f"{request.min_cross_sectional_samples})."
                )

            factor_matrices[factor_def.factor_id] = FactorNormalizer.normalize_cross_section(values)
            factor_value_trace[factor_def.factor_id] = {
                v.symbol: {"raw_value": v.raw_value, "status": v.status.value} for v in values
            }

        # --- Control 11: composite signal (MultiFactorEngine -> SignalEngine) -----------------
        multi_factor_engine = MultiFactorEngine(sorted_signal_config)
        composite_scores = multi_factor_engine.compute_composite_scores(factor_matrices)
        signal_label = "composite:" + "+".join(resolved_factor_ids)
        signals = SignalEngine.generate_signals(composite_scores, signal_label, as_of_date_str)

        # --- Control 12: portfolio construction — NO hard-coded equal-weight in this executor -
        top_n = request.parameters.get("top_n")
        if not isinstance(top_n, int) or isinstance(top_n, bool) or top_n < 1:
            raise ValueError("FAIL CLOSED: parameters['top_n'] must be an explicit positive integer.")
        strategy = GenericFactorStrategy()
        raw_weights = strategy.generate_target_portfolio(signals, top_n=top_n)
        portfolio_target = PortfolioConstructor.build_portfolio(
            raw_weights, as_of_date_str, request.strategy_id, request.security_master
        )

        # --- Control 13: parameter / cost-model binding — explicit, non-empty -----------------
        if not request.parameters:
            raise ValueError("FAIL CLOSED: parameters must be explicitly supplied and non-empty.")
        if not request.cost_model_config:
            raise ValueError("FAIL CLOSED: cost_model_config must be explicitly supplied and non-empty.")

        # --- Control 14: code version / working-tree state (must be determinable) -------------
        code_version, code_state = get_code_version(request.code_repo_dir)
        if code_version == "UNAVAILABLE" or code_state == "UNAVAILABLE":
            raise ValueError(
                "FAIL CLOSED: could not determine code_version/code_state (git unavailable in "
                "this environment). A certified research run requires a known code identity."
            )

        # --- Execute: pure numeric simulation on the ADJUSTED series with the REAL, signal- ---
        # -----derived portfolio weights (Phase 8A-hardened BacktestEngine genuinely consumes them)
        try:
            cost_model = TransactionCostModel(**request.cost_model_config)
        except TypeError as e:
            raise ValueError(
                f"FAIL CLOSED: cost_model_config does not match TransactionCostModel's fields "
                f"({[f.name for f in TransactionCostModel.__dataclass_fields__.values()]}): {e}"
            )

        engine = BacktestEngine(cost_model=cost_model)
        backtest_result = engine.run_backtest(
            dataset_id=request.dataset_id, strategy_id=request.strategy_id,
            daily_prices=adjusted_prices, portfolio_targets=[portfolio_target],
            snapshot_id=request.snapshot_id, as_of=request.as_of,
        )

        # --- Bind every control into the immutable identity/manifest -------------------------
        universe_hash = compute_canonical_sha256(universe_symbols_sorted)
        factors_config_dicts = [{"factor_id": s.factor_id, "parameters": s.parameters} for s in sorted_specs]
        factor_hash = compute_canonical_sha256(factors_config_dicts)
        signal_config_dicts = [
            {"factor_name": c.factor_name, "weight": c.weight, "direction": c.direction.value}
            for c in sorted_signal_config
        ]
        signal_configuration_hash = compute_canonical_sha256({
            "signal_config": signal_config_dicts,
            "min_cross_sectional_samples": request.min_cross_sectional_samples,
        })
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
            factors_config=factors_config_dicts,
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
            signal_config=signal_config_dicts,
            signal_configuration_hash=signal_configuration_hash,
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
            signal_configuration_hash=signal_configuration_hash,
        )

        # --- Immutable write — fails closed on research_run_id collision (Phase 7A behavior) -
        artifacts = {
            "daily_prices": adjusted_prices,
            "raw_daily_prices": raw_prices_used,
            "dates": dates_used,
            "corporate_actions_applied": adjustment_trace,
            "dataset_directory": request.dataset_directory,
            "provider_data_origin": request.provider_data_origin,
            "fundamental_data": request.fundamental_data,
            "factor_values": factor_value_trace,
            "portfolio_weights": raw_weights,
        }
        request.run_store.create_run(identity, input_manifest, result_manifest, artifacts)

        return backtest_result, identity
