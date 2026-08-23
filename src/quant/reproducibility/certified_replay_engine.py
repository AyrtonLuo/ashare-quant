"""
certified_replay_engine.py — Replay verification for runs created via CertifiedResearchRunExecutor.

Phase 7J built the first two re-verification layers (persistent dataset bytes, corporate-action
data). Phase 8A extends this to the full factor/signal/portfolio chain: CertifiedReplayEngine
does NOT delegate its final backtest re-execution to ResearchReplayEngine (Phase 7A) anymore for
certified runs, because ResearchReplayEngine reconstructs a generic equal-weight PortfolioTarget
from whatever symbols happen to be in the stored price artifact — it has no notion of factors,
signals, or the real weights a certified run actually used. A genuinely certified replay must
re-derive those real weights from source and use THEM in the final backtest, not an unrelated
equal-weight approximation.

Two distinct failure classes are raised, on purpose:

  IntermediateArtifactMismatchError — raised the moment ANY re-verified/recomputed step (dataset
  bytes, corporate-action-adjusted prices, factor values, normalized scores, composite signal,
  or portfolio weights) diverges from what was certified. This pinpoints WHERE reproducibility
  broke (e.g. "the FactorRegistry's momentum implementation changed" vs. "the dataset was
  tampered with") — a real diagnostic improvement over one undifferentiated MISMATCH.

  ReplayStatus.MISMATCH (returned, not raised) — reserved for the case where every intermediate
  step reproduces exactly, but the final BacktestEngine result_hash still differs. That would
  indicate a BacktestEngine/TransactionCostModel-level reproducibility bug, not a factor bug.

Never reads cached factor values, signals, or portfolio weights as a computation INPUT — they
are consulted only as comparison targets, after being independently recomputed from source.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from src.quant.reproducibility.store import ResearchRunStore
from src.quant.reproducibility.persistent_dataset_lock import PersistentDatasetLock
from src.quant.reproducibility.dataset_lock import DatasetVersionLock
from src.quant.backtest.engine import BacktestEngine
from src.quant.backtest.cost_model import TransactionCostModel
from src.quant.portfolio.construction import PortfolioConstructor
from src.quant.reproducibility.canonical import compute_canonical_sha256
from src.data.domain.persistent_manifest import PersistentDatasetManifestStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.data.domain.security_master import SecurityMasterRegistry
from src.data.revision.corporate_action_store import CorporateActionStore
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.validation.pit_gate import PITGate
from src.quant.adjustment.corporate_action_adjuster import CorporateActionAdjuster
from src.quant.factors.registry import FactorRegistry, FactorSpec, DATA_SOURCE_MARKET, DATA_SOURCE_FUNDAMENTAL
from src.quant.factors.base import FactorValue, FactorStatus
from src.quant.factors.normalization import FactorNormalizer
from src.quant.factors.multi_factor import MultiFactorEngine, FactorWeightConfig, FactorDirection
from src.quant.signals.engine import SignalEngine
from src.quant.strategies.generic_factor_strategy import GenericFactorStrategy


class IntermediateArtifactMismatchError(ValueError):
    """A re-verified or recomputed intermediate step (dataset, corp-action, factor, signal, or
    portfolio) diverges from what was certified — distinct from a FINAL_RESULT_MISMATCH, which
    is reserved for the backtest/result-hash step succeeding on identical intermediate inputs."""
    pass


class ReplayStatus(str, Enum):
    REPRODUCIBLE = "REPRODUCIBLE"
    FINAL_RESULT_MISMATCH = "FINAL_RESULT_MISMATCH"


@dataclass(frozen=True)
class CertifiedReplayReport:
    research_run_id: str
    status: ReplayStatus
    original_result_hash: str
    replayed_result_hash: str
    explanation: str


class CertifiedReplayEngine:
    def __init__(
        self,
        run_store: ResearchRunStore,
        snapshot_manager: SnapshotManager,
        persistent_manifest_store: PersistentDatasetManifestStore,
        corporate_action_store: CorporateActionStore,
        security_master: SecurityMasterRegistry,
        fundamental_data: Dict[str, List[FundamentalDataContract]],
    ):
        self.run_store = run_store
        self.snapshot_manager = snapshot_manager
        self.persistent_manifest_store = persistent_manifest_store
        self.corporate_action_store = corporate_action_store
        self.security_master = security_master
        self.fundamental_data = fundamental_data

    def replay(self, research_run_id: str) -> CertifiedReplayReport:
        run_data = self.run_store.get_run(research_run_id)
        if not run_data:
            raise KeyError(f"FAIL CLOSED: Research Run '{research_run_id}' not found in store.")

        identity = run_data["identity"]
        input_manifest = run_data["input_manifest"]
        result_manifest = run_data["result_manifest"]
        artifacts = run_data.get("artifacts", {})
        as_of = datetime.fromisoformat(input_manifest.as_of)
        as_of_date_str = as_of.strftime("%Y-%m-%d")

        dataset_directory = artifacts.get("dataset_directory")
        if not dataset_directory:
            raise RuntimeError(
                f"FAIL CLOSED: Research Run '{research_run_id}' has no recorded dataset_directory "
                "artifact — cannot re-verify the persistent dataset it was certified against."
            )

        # --- Re-verify 1: persistent dataset artifact still matches its certified hash --------
        locked_persistent = PersistentDatasetLock.lock(
            input_manifest.dataset_id, input_manifest.dataset_version, dataset_directory,
            self.persistent_manifest_store,
        )
        if locked_persistent.content_sha256 != input_manifest.dataset_manifest_hash:
            raise IntermediateArtifactMismatchError(
                f"FAIL CLOSED (INTERMEDIATE_ARTIFACT_MISMATCH): persistent dataset content_sha256 "
                f"at replay time ('{locked_persistent.content_sha256}') does not match the hash "
                f"recorded at certification time ('{input_manifest.dataset_manifest_hash}') for "
                f"run '{research_run_id}'. The dataset changed after certification."
            )

        # --- Re-verify 2: snapshot / dataset-version lock still resolves, as_of still matches --
        locked_snapshot = DatasetVersionLock.lock(
            input_manifest.dataset_version, input_manifest.snapshot_id, self.snapshot_manager,
        )
        if datetime.fromisoformat(locked_snapshot.as_of) != as_of:
            raise IntermediateArtifactMismatchError(
                f"FAIL CLOSED (INTERMEDIATE_ARTIFACT_MISMATCH): snapshot '{input_manifest.snapshot_id}' "
                f"as_of at replay time ('{locked_snapshot.as_of}') no longer matches the certified "
                f"as_of ('{input_manifest.as_of}') for run '{research_run_id}'."
            )

        # --- Re-verify 3: historical universe reconstruction — every certified symbol must still
        # be PIT-tradable as of the certified as_of, under the CURRENT security master state -----
        for symbol in input_manifest.universe_symbols:
            if not self.security_master.is_tradable_on(symbol, as_of_date_str):
                raise IntermediateArtifactMismatchError(
                    f"FAIL CLOSED (INTERMEDIATE_ARTIFACT_MISMATCH): symbol '{symbol}' from run "
                    f"'{research_run_id}''s certified universe is no longer PIT-tradable as of "
                    f"{as_of_date_str} under the current security master state."
                )

        # --- Re-verify 4: corporate-action-adjusted price series still matches -----------------
        raw_prices = artifacts.get("raw_daily_prices")
        dates = artifacts.get("dates")
        original_adjusted = artifacts.get("daily_prices")
        original_weights = artifacts.get("portfolio_weights")
        if not raw_prices or not dates or not original_adjusted or original_weights is None:
            raise RuntimeError(
                f"FAIL CLOSED: Research Run '{research_run_id}' is missing raw_daily_prices/dates/"
                "daily_prices/portfolio_weights artifacts — cannot re-verify this run end to end."
            )

        for symbol in input_manifest.universe_symbols:
            if symbol not in raw_prices or symbol not in dates:
                raise RuntimeError(
                    f"FAIL CLOSED: Research Run '{research_run_id}' is missing raw price data for "
                    f"universe symbol '{symbol}'."
                )
            symbol_dates = dates[symbol]
            symbol_raw = raw_prices[symbol]
            visible_actions = self.corporate_action_store.query_pit_range(
                symbol, symbol_dates[0], symbol_dates[-1], as_of
            )
            # Replay must recompute under the algorithm THIS run was actually certified with,
            # never "whatever is current" (CORPORATE_ACTION_UNIFIED_FORMULA_ARCHITECTURE_
            # PROPOSAL.md, CEO-approved) — read from the run's own stored input_manifest, not
            # the function's legacy default, so a future algorithm change can never silently
            # alter a past run's replay behavior.
            recomputed_adj = CorporateActionAdjuster.adjust(
                symbol_dates, symbol_raw, visible_actions, as_of,
                algorithm_version=input_manifest.adjustment_algorithm_version,
            )
            if recomputed_adj.adjusted_prices != original_adjusted.get(symbol):
                raise IntermediateArtifactMismatchError(
                    f"FAIL CLOSED (INTERMEDIATE_ARTIFACT_MISMATCH): corporate-action-adjusted "
                    f"price series for '{symbol}' in run '{research_run_id}' no longer matches "
                    "what was certified. Corporate-action data (or the raw inputs) changed since "
                    "certification."
                )

        # --- Re-verify 5: factor calculation, recomputed from FactorRegistry + re-verified data
        factor_specs = [FactorSpec(d["factor_id"], d["parameters"]) for d in input_manifest.factors_config]
        resolved_factors = FactorRegistry.resolve_all(factor_specs)

        signal_config = [
            FactorWeightConfig(d["factor_name"], d["weight"], FactorDirection(d["direction"]))
            for d in input_manifest.signal_config
        ]

        factor_matrices: Dict[str, Dict[str, float]] = {}
        for factor_instance, factor_def in resolved_factors:
            values: List[FactorValue] = []
            if factor_def.data_source == DATA_SOURCE_MARKET:
                for symbol in input_manifest.universe_symbols:
                    values.append(
                        factor_instance.compute(symbol, original_adjusted[symbol], as_of_date_str, as_of)
                    )
            elif factor_def.data_source == DATA_SOURCE_FUNDAMENTAL:
                for symbol in input_manifest.universe_symbols:
                    records = self.fundamental_data.get(symbol, [])
                    pit_visible = PITGate.filter_pit_fundamentals(records, as_of)
                    if not pit_visible:
                        values.append(FactorValue(
                            symbol=symbol, factor_name=factor_def.factor_id, factor_version="n/a",
                            raw_value=None, effective_date=as_of_date_str, as_of=as_of,
                            status=FactorStatus.NOT_APPLICABLE,
                            quality_notes="no PIT-visible fundamental record at replay time",
                        ))
                        continue
                    selected = max(pit_visible, key=lambda r: (r.report_date, r.available_at))
                    metric_type = getattr(factor_instance, "metric_type", None)
                    val = getattr(selected, metric_type, None) if metric_type else None
                    values.append(
                        factor_instance.compute_from_fundamental(
                            symbol, val, selected.provenance, as_of_date_str, as_of
                        )
                    )
            factor_matrices[factor_def.factor_id] = FactorNormalizer.normalize_cross_section(values)

        # --- Re-verify 6: composite signal + portfolio weights, compared to the certified artifact
        multi_factor_engine = MultiFactorEngine(signal_config)
        composite_scores = multi_factor_engine.compute_composite_scores(factor_matrices)
        signal_label = "composite:" + "+".join(sorted(d.factor_id for _, d in resolved_factors))
        signals = SignalEngine.generate_signals(composite_scores, signal_label, as_of_date_str)

        top_n = input_manifest.strategy_parameters.get("top_n")
        recomputed_weights = GenericFactorStrategy().generate_target_portfolio(signals, top_n=top_n)

        if recomputed_weights != original_weights:
            raise IntermediateArtifactMismatchError(
                f"FAIL CLOSED (INTERMEDIATE_ARTIFACT_MISMATCH): recomputed portfolio weights for "
                f"run '{research_run_id}' diverge from the certified artifact. "
                f"original={original_weights} recomputed={recomputed_weights}"
            )

        # --- Reconstruct the exact certified cost model (Phase 7J fix, unchanged) --------------
        try:
            cost_model = TransactionCostModel(**input_manifest.cost_model_config)
        except TypeError as e:
            raise ValueError(
                f"FAIL CLOSED: stored cost_model_config for run '{research_run_id}' no longer "
                f"matches TransactionCostModel's fields: {e}"
            )

        # --- Final step: re-execute the backtest with the RECOMPUTED (not cached) weights ------
        portfolio_target = PortfolioConstructor.build_portfolio(
            recomputed_weights, as_of_date_str, input_manifest.strategy_id, self.security_master
        )
        engine = BacktestEngine(cost_model=cost_model)
        backtest_res = engine.run_backtest(
            dataset_id=locked_snapshot.dataset_version, strategy_id=input_manifest.strategy_id,
            daily_prices=original_adjusted, portfolio_targets=[portfolio_target],
            snapshot_id=locked_snapshot.snapshot_id, as_of=as_of,
        )

        replayed_payload = {
            "sharpe": backtest_res.sharpe_ratio,
            "return": backtest_res.total_return,
            "mdd": backtest_res.max_drawdown,
        }
        replayed_hash = compute_canonical_sha256(replayed_payload)
        original_hash = identity.result_hash or result_manifest.result_hash

        if replayed_hash == original_hash:
            return CertifiedReplayReport(
                research_run_id=research_run_id, status=ReplayStatus.REPRODUCIBLE,
                original_result_hash=original_hash, replayed_result_hash=replayed_hash,
                explanation="REPRODUCIBLE: dataset, snapshot, universe, corporate actions, "
                            "factors, signal, and portfolio all recomputed identically; final "
                            "result hash matches.",
            )
        return CertifiedReplayReport(
            research_run_id=research_run_id, status=ReplayStatus.FINAL_RESULT_MISMATCH,
            original_result_hash=original_hash, replayed_result_hash=replayed_hash,
            explanation=f"FINAL_RESULT_MISMATCH: every intermediate artifact reproduced "
                        f"identically, but the backtest result hash still differs "
                        f"('{replayed_hash}' != '{original_hash}') — indicates a "
                        "BacktestEngine/TransactionCostModel-level reproducibility issue, not a "
                        "factor/signal/portfolio issue.",
        )
