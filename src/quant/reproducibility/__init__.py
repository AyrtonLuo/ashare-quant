"""
Reproducibility package initialization.
"""

from src.quant.reproducibility.canonical import to_canonical_json, compute_canonical_sha256
from src.quant.reproducibility.identity import ResearchRunIdentity, get_code_version
from src.quant.reproducibility.dataset_lock import DatasetVersionLock, LockedDatasetState
from src.quant.reproducibility.manifest import (
    ResearchRunManifest, ResearchRunManager, ResearchInputManifest, ResearchResultManifest
)
from src.quant.reproducibility.comparator import ResearchResultComparator, ComparisonStatus, RunComparisonReport
from src.quant.reproducibility.store import ResearchRunStore
from src.quant.reproducibility.replay_engine import ResearchReplayEngine, ReplayStatus, ReplayReport

__all__ = [
    "to_canonical_json",
    "compute_canonical_sha256",
    "ResearchRunIdentity",
    "get_code_version",
    "DatasetVersionLock",
    "LockedDatasetState",
    "ResearchRunManifest",
    "ResearchRunManager",
    "ResearchInputManifest",
    "ResearchResultManifest",
    "ResearchResultComparator",
    "ComparisonStatus",
    "RunComparisonReport",
    "ResearchRunStore",
    "ResearchReplayEngine",
    "ReplayStatus",
    "ReplayReport"
]
