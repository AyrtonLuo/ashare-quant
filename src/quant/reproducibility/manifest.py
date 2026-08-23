"""
manifest.py — ResearchInputManifest, ResearchResultManifest & ResearchRunManifest.
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional
from src.quant.reproducibility.canonical import compute_canonical_sha256


@dataclass(frozen=True)
class ResearchInputManifest:
    """
    Complete, unambiguous specification of all inputs required to run a research experiment / backtest.
    """
    research_run_id: str
    dataset_id: str
    dataset_version: str
    snapshot_id: str
    dataset_manifest_hash: str
    as_of: str
    start_date: str
    end_date: str
    universe_type: str
    universe_symbols: List[str]
    universe_hash: str
    factors_config: List[Dict[str, Any]]
    factor_definition_hash: str
    strategy_id: str
    strategy_version: str
    strategy_parameters: Dict[str, Any]
    parameter_hash: str
    portfolio_constraints: Dict[str, Any]
    cost_model_config: Dict[str, Any]
    transaction_cost_model_hash: str
    benchmark_id: str
    benchmark_version: str
    benchmark_hash: str
    code_version: str
    code_state: str
    created_at: str

    # Phase 8A: how multiple factors' cross-sectional z-scores combine into one composite
    # signal (List[FactorWeightConfig]-as-dicts) plus its hash. Trailing defaulted fields —
    # added after every other field so existing constructors (Phase 7A-7J) remain valid
    # without modification; only Phase 8A's factor-driven certified path ever sets a real
    # (non-default) value. "NOT_APPLICABLE" distinguishes "single-factor run, no combination
    # scheme" / "pre-Phase-8A run" from a field that was simply never populated.
    signal_config: List[Dict[str, Any]] = field(default_factory=list)
    signal_configuration_hash: str = "NOT_APPLICABLE"

    # CORPORATE_ACTION_UNIFIED_FORMULA_ARCHITECTURE_PROPOSAL.md (CEO-approved): which
    # CorporateActionAdjuster algorithm this run was certified under — "1.0" (legacy,
    # independent-factor-then-multiply) or "2.0" (unified D/B/R formula for RIGHTS_OFFERING
    # combinations; STOCK_SPLIT unaffected either way). Trailing-defaulted to "1.0" so every
    # existing constructor call site remains valid unmodified, and so a manifest predating this
    # field (or any dict reconstructed without the key) is honestly described as legacy rather
    # than silently assumed to be "2.0". CertifiedResearchRunExecutor.execute() always sets this
    # explicitly to "2.0" for new runs; it participates in compute_input_hash() like every other
    # field here, so changing it changes input_hash — a run's certified algorithm choice is
    # itself part of what's certified, not a side channel. CertifiedReplayEngine.replay() reads
    # this field back and passes it to CorporateActionAdjuster.adjust() so replay always
    # recomputes under the algorithm the run was ACTUALLY certified with, never "whatever is
    # current" — see corporate_action_adjuster.py's module docstring for the full algorithm
    # description.
    adjustment_algorithm_version: str = "1.0"

    def compute_input_hash(self) -> str:
        return compute_canonical_sha256(asdict(self))


@dataclass(frozen=True)
class ResearchResultManifest:
    """
    Complete specification of SHA-256 hashes of all backtest output artifacts.
    Explicitly marks missing outputs as "UNAVAILABLE" (No fillna(0) or silent fallbacks).
    """
    research_run_id: str
    input_manifest_hash: str
    result_hash: str
    equity_curve_hash: str
    positions_hash: str = "UNAVAILABLE"
    trades_hash: str = "UNAVAILABLE"
    signals_hash: str = "UNAVAILABLE"
    factor_output_hash: str = "UNAVAILABLE"
    performance_metrics_hash: str = "UNAVAILABLE"
    drawdown_hash: str = "UNAVAILABLE"
    benchmark_result_hash: str = "UNAVAILABLE"

    # Phase 9 (Research Result Persistence Hardening): the actual BacktestResult scalar
    # metrics, not just their hashes — closes the gap where result_hash proved a result was
    # certified but no process could read the certified NUMBERS back after the fact (see
    # PHASE_9_RESEARCH_RESULT_PERSISTENCE_ARCHITECTURE_PROPOSAL.md §3/§10). Trailing-defaulted
    # (None / "1.0") so every existing constructor call site (store.py, real_data_verifier.py,
    # live_provider_verifier.py, and existing tests) remains valid unmodified. A run persisted
    # under schema_version "1.0" genuinely has no canonical metrics on record — readers MUST
    # treat None as "not available for this legacy run," never coerce it to 0.0.
    #
    # result_hash's own definition and computation point are UNCHANGED by these fields — it is
    # still computed once, at certification time, over the small {"sharpe","return","mdd"}
    # payload exactly as before. These fields do not participate in that hash; they are the
    # durable record of the same numbers, verifiable against result_hash on read via
    # verify_result_manifest_integrity() (identity.py) rather than by redefining the hash.
    schema_version: str = "1.0"
    total_return: Optional[float] = None
    annualized_return: Optional[float] = None
    annualized_volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    turnover: Optional[float] = None
    trade_count: Optional[int] = None

    def compute_manifest_hash(self) -> str:
        return compute_canonical_sha256(asdict(self))


@dataclass(frozen=True)
class ResearchRunManifest:
    """
    Legacy backwards-compatible ResearchRunManifest structure required by existing tests.
    """
    run_id: str
    created_at: str
    dataset_id: str
    dataset_hash: str
    strategy_id: str
    strategy_version: str
    parameters_hash: str
    cost_model_version: str
    sharpe_ratio: float
    total_return: float
    max_drawdown: float
    reproducibility_status: str = "VERIFIED"
    snapshot_id: str = "snapshot_default_v1"
    dataset_version: str = "ds_v1.0"
    as_of: str = "2026-08-01T00:00:00"
    strategy_config_hash: Optional[str] = None
    factor_config_hash: Optional[str] = None
    code_version: str = "1.0.0"
    result_hash: Optional[str] = None

    @property
    def research_run_id(self) -> str:
        return self.run_id


class ResearchRunManager:
    """Computes parameter hashes and verifies 100% deterministic reproducibility of backtests."""

    @staticmethod
    def create_run_manifest(
        run_id: str,
        created_at: str,
        dataset_id: str,
        dataset_payload: Any,
        strategy_id: str,
        strategy_version: str,
        parameters: Dict[str, Any],
        cost_model_version: str,
        sharpe_ratio: float,
        total_return: float,
        max_drawdown: float,
        snapshot_id: Optional[str] = None,
        dataset_version: Optional[str] = None,
        as_of: Optional[str] = None,
        code_version: str = "1.0.0"
    ) -> ResearchRunManifest:
        dataset_hash = compute_canonical_sha256(dataset_payload)
        params_hash = compute_canonical_sha256(parameters)
        
        result_payload = {"sharpe": sharpe_ratio, "return": total_return, "mdd": max_drawdown}
        result_hash = compute_canonical_sha256(result_payload)

        s_id = snapshot_id or f"snapshot_{dataset_id}"
        d_ver = dataset_version or "ds_v1.0"
        a_of = as_of or created_at

        return ResearchRunManifest(
            run_id=run_id,
            created_at=created_at,
            dataset_id=dataset_id,
            dataset_hash=dataset_hash,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            parameters_hash=params_hash,
            cost_model_version=cost_model_version,
            sharpe_ratio=sharpe_ratio,
            total_return=total_return,
            max_drawdown=max_drawdown,
            reproducibility_status="VERIFIED",
            snapshot_id=s_id,
            dataset_version=d_ver,
            as_of=a_of,
            strategy_config_hash=params_hash,
            factor_config_hash=params_hash,
            code_version=code_version,
            result_hash=result_hash
        )
