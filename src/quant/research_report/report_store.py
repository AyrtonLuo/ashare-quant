"""
report_store.py — ResearchAnalystReportStore: immutable persistence for AI Research Analyst
reports.

AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §11 Step 5. A deliberate mirror of
`ResearchRunStore` (src/quant/reproducibility/store.py): same immutability rule, same
atomic temp-directory-then-rename write, same FAIL CLOSED corruption handling on read, same
in-memory cache in front of disk, same `to_canonical_json` serialization. It is a separate
store rather than an extension of `ResearchRunStore` because a report is a different artifact
with a different reproducibility contract — see report_identity.py's docstring — and because
extending the certified-run store would have meant touching `result_hash`-bearing code that
this directive explicitly forbids modifying.

Layout, one directory per report under `base_dir/<report_id>/`:
  report_metadata.json   — the ResearchAnalystReportIdentity
  structured_output.json — the validated StructuredResearchOutput (the AI prose)
  evidence_bundle.json   — the canonical Evidence Bundle payload that was hashed and sent

The Evidence Bundle is persisted alongside the report on purpose: without it,
`evidence_bundle_hash` would be an unverifiable number. With it,
`verify_report_evidence_integrity()` can re-derive the hash at any later date and prove the
evidence has not been altered — which is the entire deterministic guarantee this artifact is
entitled to claim.
"""

import json
import os
import shutil
import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from src.llm.structured_output import StructuredResearchOutput
from src.quant.reproducibility.canonical import compute_canonical_sha256, to_canonical_json
from src.quant.research_report.report_identity import ResearchAnalystReportIdentity


class ResearchAnalystReportStore:
    """Manages immutable persistence of AI Research Analyst reports under
    data/research/analyst_reports/<report_id>/. Overwriting an existing report fails closed."""

    def __init__(self, base_dir: str = "/Users/yuhanluo/ashare-quant/data/research/analyst_reports"):
        self.base_dir = base_dir
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        os.makedirs(self.base_dir, exist_ok=True)

    def create_report(
        self,
        identity: ResearchAnalystReportIdentity,
        output: StructuredResearchOutput,
        evidence_payload: List[Dict[str, Any]],
    ) -> str:
        report_id = identity.report_id
        report_path = os.path.join(self.base_dir, report_id)

        if report_id in self._memory_store or os.path.exists(report_path):
            raise ValueError(
                f"FAIL CLOSED: Research Analyst Report ID '{report_id}' already exists and is "
                "IMMUTABLE. Mutating or overwriting a past report is strictly prohibited."
            )

        if not evidence_payload:
            raise ValueError(
                "FAIL CLOSED: refusing to persist a report with an empty Evidence Bundle — the "
                "stored evidence_bundle_hash would be unverifiable."
            )

        # Persisting an identity whose hash does not describe the bundle stored next to it would
        # create a report that fails its own integrity check forever after, with no way to tell
        # tampering from a bad write. Caught here, at the only point where the two are paired.
        if compute_canonical_sha256(evidence_payload) != identity.evidence_bundle_hash:
            raise ValueError(
                "FAIL CLOSED: evidence_bundle_hash on the identity does not match the Evidence "
                "Bundle being persisted with it. Refusing to store a self-inconsistent report."
            )

        # The orchestration layer already ran validate_citations() before this output existed;
        # this re-check exists because create_report() is a public entry point that a future
        # caller could reach without going through generate_ai_research_output(). It never
        # repairs or drops a citation — it refuses the write.
        payload_ids = {item.get("evidence_id") for item in evidence_payload}
        dangling = [e for e in output.evidence_ids if e not in payload_ids]
        if dangling:
            raise ValueError(
                f"FAIL CLOSED: report cites evidence_id(s) {dangling} that are absent from the "
                "Evidence Bundle being persisted with it."
            )

        report_data = {
            "identity": identity,
            "output": output,
            "evidence_payload": list(evidence_payload),
        }

        # Same atomic-write hardening as ResearchRunStore.create_run() (Phase 9): write into a
        # uniquely-named temp directory and os.rename it into place, so a crash mid-write can
        # never leave a partially-written directory under the final report_id name.
        tmp_path = f"{report_path}.tmp-{uuid.uuid4().hex}"
        try:
            os.makedirs(tmp_path, exist_ok=False)
            with open(os.path.join(tmp_path, "report_metadata.json"), "w") as f:
                f.write(to_canonical_json(asdict(identity)))
            with open(os.path.join(tmp_path, "structured_output.json"), "w") as f:
                f.write(to_canonical_json(asdict(output)))
            with open(os.path.join(tmp_path, "evidence_bundle.json"), "w") as f:
                f.write(to_canonical_json(list(evidence_payload)))

            os.rename(tmp_path, report_path)
        except Exception as e:
            shutil.rmtree(tmp_path, ignore_errors=True)
            if os.path.exists(report_path):
                raise ValueError(
                    f"FAIL CLOSED: Research Analyst Report ID '{report_id}' already exists and "
                    "is IMMUTABLE. Mutating or overwriting a past report is strictly prohibited."
                ) from e
            raise

        self._memory_store[report_id] = report_data
        return report_id

    def _load_json(self, report_id: str, report_path: str, filename: str) -> Any:
        """Corrupted persisted files fail closed with a clear message rather than raising an
        opaque JSONDecodeError from deep inside get_report() — same convention as
        ResearchRunStore._load_json(). Never recovers or guesses at missing content."""
        path = os.path.join(report_path, filename)
        try:
            with open(path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"FAIL CLOSED: corrupted persisted file for report '{report_id}': {path} ({e})"
            ) from e

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        if report_id in self._memory_store:
            return self._memory_store[report_id]

        report_path = os.path.join(self.base_dir, report_id)
        if not os.path.exists(report_path):
            return None

        identity = ResearchAnalystReportIdentity(
            **self._load_json(report_id, report_path, "report_metadata.json")
        )
        output = StructuredResearchOutput(
            **self._load_json(report_id, report_path, "structured_output.json")
        )
        evidence_payload = self._load_json(report_id, report_path, "evidence_bundle.json")

        report_data = {
            "identity": identity,
            "output": output,
            "evidence_payload": evidence_payload,
        }
        self._memory_store[report_id] = report_data
        return report_data

    def list_reports(self) -> List[str]:
        report_ids = set(self._memory_store.keys())
        if os.path.exists(self.base_dir):
            report_ids.update(os.listdir(self.base_dir))
        return sorted(report_ids)

    def get_identity(self, report_id: str) -> Optional[ResearchAnalystReportIdentity]:
        report = self.get_report(report_id)
        return report["identity"] if report else None

    def get_evidence_payload(self, report_id: str) -> Optional[List[Dict[str, Any]]]:
        report = self.get_report(report_id)
        return report["evidence_payload"] if report else None
