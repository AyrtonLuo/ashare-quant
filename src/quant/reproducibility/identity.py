"""
identity.py — ResearchRunIdentity Dataclass & Code Version Inspection.
"""

import subprocess
from dataclasses import dataclass
from typing import Dict, Any, Tuple

from src.quant.reproducibility.canonical import compute_canonical_sha256


def get_code_version(cwd: str = "/Users/yuhanluo/ashare-quant") -> Tuple[str, str]:
    """
    Returns (git_commit_hash, code_state) where code_state is "CLEAN", "DIRTY", or "UNAVAILABLE".
    """
    try:
        commit_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        git_commit = commit_res.stdout.strip()
        
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        is_dirty = bool(status_res.stdout.strip())
        code_state = "DIRTY" if is_dirty else "CLEAN"
        return git_commit, code_state
    except Exception:
        return "UNAVAILABLE", "UNAVAILABLE"


@dataclass(frozen=True)
class ResearchRunIdentity:
    """
    Immutable identity of a quantitative research / backtest execution run.
    Guarantees 100% complete parameter and artifact provenance.
    """
    research_run_id: str
    snapshot_id: str
    dataset_version: str
    dataset_manifest_hash: str
    as_of: str
    start_date: str
    end_date: str
    universe_definition: Dict[str, Any]
    universe_hash: str
    strategy_id: str
    strategy_version: str
    factor_definition_hash: str
    parameter_hash: str
    transaction_cost_model_hash: str
    benchmark_id: str
    code_version: str
    code_state: str
    input_hash: str
    result_hash: str
    created_at: str

    # Phase 8A: hash of how multiple factors' cross-sectional z-scores combine into one
    # composite signal. Trailing defaulted field so every existing (Phase 7A-7J) constructor
    # of ResearchRunIdentity remains valid unmodified; only Phase 8A's factor-driven certified
    # path ever sets a real value. Mirrors factor_definition_hash's existing pattern.
    signal_configuration_hash: str = "NOT_APPLICABLE"


def verify_result_manifest_integrity(identity: ResearchRunIdentity, result_manifest: Any) -> bool:
    """Phase 9 (Research Result Persistence Hardening): an OPT-IN integrity check, never called
    automatically inside ResearchRunStore.get_run() — recomputes result_hash from the persisted
    ResearchResultManifest's own scalar fields and compares it against identity.result_hash.

    This does NOT redefine what result_hash covers or how/when it's computed (still the small
    {"sharpe","return","mdd"} payload, computed once at certification time in
    CertifiedResearchRunExecutor.execute() — unchanged). It answers a different, new question:
    "does the full persisted result_manifest.json still agree with the identity file next to
    it?" — catching independent tampering/corruption of one file without the other, which
    nothing checked before Phase 9.

    Returns False (not an exception) for a schema_version "1.0" manifest — a legacy run has no
    scalar fields to verify against; that is a known, honest limitation (see
    PHASE_9_RESEARCH_RESULT_PERSISTENCE_ARCHITECTURE_PROPOSAL.md §15), not a tamper signal.
    """
    if getattr(result_manifest, "schema_version", "1.0") == "1.0":
        return False
    if result_manifest.total_return is None or result_manifest.sharpe_ratio is None or result_manifest.max_drawdown is None:
        return False
    recomputed = compute_canonical_sha256({
        "sharpe": result_manifest.sharpe_ratio,
        "return": result_manifest.total_return,
        "mdd": result_manifest.max_drawdown,
    })
    return recomputed == identity.result_hash
