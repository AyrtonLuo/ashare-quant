"""
identity.py — ResearchRunIdentity Dataclass & Code Version Inspection.
"""

import subprocess
from dataclasses import dataclass
from typing import Dict, Any, Tuple


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
