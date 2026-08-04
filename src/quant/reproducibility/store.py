"""
store.py — Immutable ResearchRunStore for persistent research artifacts & manifests.
"""

import os
import json
from dataclasses import asdict
from typing import Dict, List, Optional, Any
from src.quant.reproducibility.identity import ResearchRunIdentity
from src.quant.reproducibility.manifest import ResearchInputManifest, ResearchResultManifest
from src.quant.reproducibility.comparator import ResearchResultComparator, RunComparisonReport
from src.quant.reproducibility.canonical import to_canonical_json


class ResearchRunStore:
    """
    Manages immutable persistence of Research Runs under data/research/runs/<research_run_id>/.
    Enforces strict immutability: mutating or overwriting an existing run fails closed.
    """

    def __init__(self, base_dir: str = "/Users/yuhanluo/ashare-quant/data/research/runs"):
        self.base_dir = base_dir
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        os.makedirs(self.base_dir, exist_ok=True)

    def create_run(
        self,
        identity: ResearchRunIdentity,
        input_manifest: ResearchInputManifest,
        result_manifest: ResearchResultManifest,
        artifacts: Optional[Dict[str, Any]] = None
    ) -> str:
        run_id = identity.research_run_id
        run_path = os.path.join(self.base_dir, run_id)

        if run_id in self._memory_store or os.path.exists(run_path):
            raise ValueError(
                f"FAIL CLOSED: Research Run ID '{run_id}' already exists and is IMMUTABLE. "
                "Mutating or overwriting past research runs is strictly prohibited."
            )

        run_data = {
            "identity": identity,
            "input_manifest": input_manifest,
            "result_manifest": result_manifest,
            "artifacts": artifacts or {}
        }
        self._memory_store[run_id] = run_data

        # Persist to disk
        os.makedirs(run_path, exist_ok=True)
        with open(os.path.join(run_path, "run_metadata.json"), "w") as f:
            f.write(to_canonical_json(asdict(identity)))
        with open(os.path.join(run_path, "input_manifest.json"), "w") as f:
            f.write(to_canonical_json(asdict(input_manifest)))
        with open(os.path.join(run_path, "result_manifest.json"), "w") as f:
            f.write(to_canonical_json(asdict(result_manifest)))

        if artifacts:
            with open(os.path.join(run_path, "artifacts.json"), "w") as f:
                f.write(to_canonical_json(artifacts))

        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        if run_id in self._memory_store:
            return self._memory_store[run_id]

        run_path = os.path.join(self.base_dir, run_id)
        if not os.path.exists(run_path):
            return None

        # Load from disk
        with open(os.path.join(run_path, "run_metadata.json"), "r") as f:
            identity_dict = json.load(f)
            identity = ResearchRunIdentity(**identity_dict)

        with open(os.path.join(run_path, "input_manifest.json"), "r") as f:
            input_dict = json.load(f)
            input_manifest = ResearchInputManifest(**input_dict)

        with open(os.path.join(run_path, "result_manifest.json"), "r") as f:
            result_dict = json.load(f)
            result_manifest = ResearchResultManifest(**result_dict)

        artifacts = {}
        art_path = os.path.join(run_path, "artifacts.json")
        if os.path.exists(art_path):
            with open(art_path, "r") as f:
                artifacts = json.load(f)

        run_data = {
            "identity": identity,
            "input_manifest": input_manifest,
            "result_manifest": result_manifest,
            "artifacts": artifacts
        }
        self._memory_store[run_id] = run_data
        return run_data

    def list_runs(self) -> List[str]:
        memory_ids = set(self._memory_store.keys())
        if os.path.exists(self.base_dir):
            disk_ids = set(os.listdir(self.base_dir))
            memory_ids.update(disk_ids)
        return sorted(list(memory_ids))

    def get_manifest(self, run_id: str) -> Optional[ResearchInputManifest]:
        run = self.get_run(run_id)
        return run["input_manifest"] if run else None

    def get_result_manifest(self, run_id: str) -> Optional[ResearchResultManifest]:
        run = self.get_run(run_id)
        return run["result_manifest"] if run else None

    def compare_runs(self, run_id_a: str, run_id_b: str) -> RunComparisonReport:
        run_a = self.get_run(run_id_a)
        run_b = self.get_run(run_id_b)

        if not run_a:
            raise KeyError(f"Run ID '{run_id_a}' not found.")
        if not run_b:
            raise KeyError(f"Run ID '{run_id_b}' not found.")

        return ResearchResultComparator.compare_runs(
            identity_a=run_a["identity"],
            identity_b=run_b["identity"],
            input_manifest_a=run_a["input_manifest"],
            input_manifest_b=run_b["input_manifest"],
            result_manifest_a=run_a["result_manifest"],
            result_manifest_b=run_b["result_manifest"]
        )
