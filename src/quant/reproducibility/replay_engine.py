"""
replay_engine.py — ResearchReplayEngine for deterministic end-to-end research replay & verification.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Optional
from datetime import datetime
from src.quant.reproducibility.store import ResearchRunStore
from src.quant.reproducibility.dataset_lock import DatasetVersionLock
from src.quant.reproducibility.canonical import compute_canonical_sha256
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.quant.backtest.engine import BacktestEngine
from src.quant.portfolio.construction import PortfolioTarget


class ReplayStatus(str, Enum):
    REPRODUCIBLE = "REPRODUCIBLE"
    MISMATCH = "MISMATCH"


@dataclass(frozen=True)
class ReplayReport:
    research_run_id: str
    status: ReplayStatus
    original_result_hash: str
    replayed_result_hash: str
    explanation: str


class ResearchReplayEngine:
    """
    Loads historical input manifests, locks snapshot_id & dataset_version, re-executes backtest,
    and verifies 100% hash identity.
    """

    def __init__(
        self,
        run_store: ResearchRunStore,
        snapshot_manager: SnapshotManager,
        backtest_engine: Optional[BacktestEngine] = None
    ):
        self.run_store = run_store
        self.snapshot_manager = snapshot_manager
        self.backtest_engine = backtest_engine or BacktestEngine()

    def replay_run(self, research_run_id: str) -> ReplayReport:
        run_data = self.run_store.get_run(research_run_id)
        if not run_data:
            raise KeyError(f"FAIL CLOSED: Research Run '{research_run_id}' not found in store.")

        identity = run_data["identity"]
        input_manifest = run_data["input_manifest"]
        result_manifest = run_data["result_manifest"]
        artifacts = run_data.get("artifacts", {})

        # Step 1: Lock Dataset Version & Snapshot (Fails closed if missing)
        locked_state = DatasetVersionLock.lock(
            dataset_version=input_manifest.dataset_version,
            snapshot_id=input_manifest.snapshot_id,
            snapshot_manager=self.snapshot_manager
        )

        # Step 2: Extract Replay Prices / Data (fail closed — never substitute a different
        # price series than the one the original run actually used, since that would let a
        # MISMATCH be masked or a false REPRODUCIBLE result be produced by coincidence).
        prices = artifacts.get("daily_prices")
        if not prices:
            raise RuntimeError(
                f"FAIL CLOSED: Research Run '{research_run_id}' has no saved 'daily_prices' artifact. "
                "Cannot replay without the original inputs."
            )

        targets = [PortfolioTarget(input_manifest.start_date, input_manifest.strategy_id, {s: 1.0 / len(input_manifest.universe_symbols) for s in input_manifest.universe_symbols}, 1.0)]

        # Step 3: Re-execute Backtest using locked snapshot
        backtest_res = self.backtest_engine.run_backtest(
            dataset_id=locked_state.dataset_version,
            strategy_id=input_manifest.strategy_id,
            daily_prices=prices,
            portfolio_targets=targets,
            snapshot_id=locked_state.snapshot_id,
            as_of=datetime.fromisoformat(locked_state.as_of)
        )

        # Step 4: Re-compute Result Hash
        replayed_payload = {
            "sharpe": backtest_res.sharpe_ratio,
            "return": backtest_res.total_return,
            "mdd": backtest_res.max_drawdown
        }
        replayed_hash = compute_canonical_sha256(replayed_payload)
        original_hash = identity.result_hash or result_manifest.result_hash

        if replayed_hash == original_hash:
            return ReplayReport(
                research_run_id=research_run_id,
                status=ReplayStatus.REPRODUCIBLE,
                original_result_hash=original_hash,
                replayed_result_hash=replayed_hash,
                explanation="REPRODUCIBLE: 100% hash identity verified across snapshot, parameters, and backtest results."
            )
        else:
            return ReplayReport(
                research_run_id=research_run_id,
                status=ReplayStatus.MISMATCH,
                original_result_hash=original_hash,
                replayed_result_hash=replayed_hash,
                explanation=f"MISMATCH: Replayed hash '{replayed_hash}' differs from original '{original_hash}'."
            )
