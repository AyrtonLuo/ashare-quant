"""
certified_replay_engine.py — Replay verification for runs created via CertifiedResearchRunExecutor.

ResearchReplayEngine (replay_engine.py, Phase 7A) re-executes a backtest from a run's stored
`daily_prices` artifact and re-locks the snapshot via DatasetVersionLock — but it trusts the
stored artifact as-is; it does not independently re-verify that the persistent dataset artifact
on disk still matches what was certified, or that the corporate-action data used to derive the
stored (adjusted) price series hasn't changed since certification. That is a real gap for a run
produced by the Phase 7J integrity gate, which explicitly binds to a real persistent artifact
and a corporate-action store.

CertifiedReplayEngine adds two independent re-verification steps BEFORE delegating to
ResearchReplayEngine's existing, already-tested hash-reproducibility check:

  1. Re-lock the persistent dataset artifact referenced by the run's own input manifest
     (dataset_id, dataset_version, dataset_manifest_hash) against its current on-disk state.
     A deleted, corrupted, or silently-replaced artifact fails closed here — the same
     PersistentDatasetLock mechanics proven in Phase 7I.
  2. Recompute the corporate-action-adjusted price series fresh from the run's stored raw
     inputs and a (possibly different, possibly since-mutated) CorporateActionStore, and
     compare it against the exact adjusted series the original run used. Any divergence
     fails closed as a corporate-action data MISMATCH — never silently replayed anyway.

Only after both pass does it hand off to ResearchReplayEngine for the final result-hash
reproducibility check.
"""

from dataclasses import dataclass
from typing import Optional

from src.quant.reproducibility.store import ResearchRunStore
from src.quant.reproducibility.replay_engine import ResearchReplayEngine, ReplayReport
from src.quant.reproducibility.persistent_dataset_lock import PersistentDatasetLock
from src.quant.backtest.engine import BacktestEngine
from src.quant.backtest.cost_model import TransactionCostModel
from src.data.domain.persistent_manifest import PersistentDatasetManifestStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.data.revision.corporate_action_store import CorporateActionStore
from src.quant.adjustment.corporate_action_adjuster import CorporateActionAdjuster
from datetime import datetime


class CertifiedReplayEngine:
    def __init__(
        self,
        run_store: ResearchRunStore,
        snapshot_manager: SnapshotManager,
        persistent_manifest_store: PersistentDatasetManifestStore,
        corporate_action_store: CorporateActionStore,
    ):
        self.run_store = run_store
        self.snapshot_manager = snapshot_manager
        self.persistent_manifest_store = persistent_manifest_store
        self.corporate_action_store = corporate_action_store

    def replay(self, research_run_id: str) -> ReplayReport:
        run_data = self.run_store.get_run(research_run_id)
        if not run_data:
            raise KeyError(f"FAIL CLOSED: Research Run '{research_run_id}' not found in store.")

        input_manifest = run_data["input_manifest"]
        artifacts = run_data.get("artifacts", {})

        dataset_directory = artifacts.get("dataset_directory")
        if not dataset_directory:
            raise RuntimeError(
                f"FAIL CLOSED: Research Run '{research_run_id}' has no recorded dataset_directory "
                "artifact — cannot re-verify the persistent dataset it was certified against."
            )

        # --- Re-verification 1: persistent dataset artifact must still match its certified hash
        locked_persistent = PersistentDatasetLock.lock(
            input_manifest.dataset_id, input_manifest.dataset_version, dataset_directory,
            self.persistent_manifest_store,
        )
        if locked_persistent.content_sha256 != input_manifest.dataset_manifest_hash:
            raise ValueError(
                f"FAIL CLOSED: persistent dataset content_sha256 at replay time "
                f"('{locked_persistent.content_sha256}') does not match the hash recorded at "
                f"certification time ('{input_manifest.dataset_manifest_hash}') for run "
                f"'{research_run_id}'. The dataset changed after certification."
            )

        # --- Re-verification 2: corporate-action-derived series must still match ---------------
        raw_prices = artifacts.get("raw_daily_prices")
        dates = artifacts.get("dates")
        original_adjusted = artifacts.get("daily_prices")
        if not raw_prices or not dates or not original_adjusted:
            raise RuntimeError(
                f"FAIL CLOSED: Research Run '{research_run_id}' is missing raw_daily_prices/dates/"
                "daily_prices artifacts — cannot re-verify corporate-action derivation."
            )

        as_of = datetime.fromisoformat(input_manifest.as_of)
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
            recomputed = CorporateActionAdjuster.adjust(symbol_dates, symbol_raw, visible_actions, as_of)
            if recomputed.adjusted_prices != original_adjusted.get(symbol):
                raise ValueError(
                    f"FAIL CLOSED: corporate-action-adjusted price series for '{symbol}' in run "
                    f"'{research_run_id}' no longer matches what was certified. Corporate-action "
                    "data (or the raw inputs) changed since certification."
                )

        # --- Reconstruct the EXACT cost model certified for this run, not the engine default --
        # ResearchReplayEngine's own default BacktestEngine() would silently use
        # TransactionCostModel()'s defaults, ignoring the cost_model_config that was actually
        # bound (and hashed) at certification time — the same "captured but not consumed" bug
        # class Phase 7I fixed for corporate actions, found here for cost models during Phase
        # 7J's second audit.
        try:
            cost_model = TransactionCostModel(**input_manifest.cost_model_config)
        except TypeError as e:
            raise ValueError(
                f"FAIL CLOSED: stored cost_model_config for run '{research_run_id}' no longer "
                f"matches TransactionCostModel's fields: {e}"
            )

        # --- Both defense-in-depth checks passed: delegate to the base replay/hash check -------
        replay_engine = ResearchReplayEngine(
            self.run_store, self.snapshot_manager, backtest_engine=BacktestEngine(cost_model=cost_model)
        )
        return replay_engine.replay_run(research_run_id)
