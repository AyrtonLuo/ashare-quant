"""
report_identity.py — ResearchAnalystReportIdentity: the immutable identity of one AI Research
Analyst report.

AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §8 (CEO-approved design), implemented as
Step 5 of that document's §11 plan. Mirrors `ResearchRunIdentity`'s established pattern
(frozen dataclass, `get_code_version()` reused verbatim, trailing-defaulted fields for anything
added after the first shipped shape, canonical SHA-256 via the one authoritative
`compute_canonical_sha256`) — it does not invent a parallel identity or hashing scheme.

THE MOST IMPORTANT PROPERTY OF THIS MODULE — the honest reproducibility scope
==============================================================================
Unlike `ResearchRunIdentity`, this identity carries **no `result_hash`**, and that omission is
deliberate, not an oversight:

  * The **Evidence Bundle is deterministically verifiable.** `evidence_bundle_hash` is
    `compute_canonical_sha256` over the exact canonical projection of the bundle that was sent
    to the provider, and `verify_report_evidence_integrity()` below re-derives it from the
    persisted bundle, catching any post-hoc tampering with the evidence.
  * The **AI-authored prose is NOT bit-reproducible, and this codebase does not claim it is.**
    An LLM is not guaranteed deterministic even given a byte-identical input; regenerating a
    report from the same `evidence_bundle_hash` may legitimately produce different wording.
    There is therefore no hash over the narrative, no "replay" of a report, and no equivalent
    of `CertifiedReplayEngine` for this artifact.

That distinction is not left to a comment: `reproducibility_scope` is a persisted, validated
field on every identity (see `REPRODUCIBILITY_SCOPE_EVIDENCE_ONLY`), so a stored report can
never be read back without the claim it is actually entitled to make travelling alongside it.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.quant.evidence.evidence_item import EvidenceItem
from src.quant.reproducibility.canonical import compute_canonical_sha256
from src.quant.reproducibility.identity import get_code_version
from src.llm.research_analyst import AIResearchOutputResult, _serialize_evidence_bundle

REPORT_IDENTITY_SCHEMA_VERSION = "1.0"

# Sentinel for provenance a provider genuinely did not supply (e.g. AlternateFakeLLMProvider
# returns model_version=None). Recording the absence explicitly is the project's established
# alternative to fabricating a plausible-looking value — same intent as ResearchRunIdentity's
# "NOT_APPLICABLE" defaults and FundamentalDataContract's NOT_APPLICABLE reporting.
NOT_REPORTED_BY_PROVIDER = "NOT_REPORTED_BY_PROVIDER"

REPRODUCIBILITY_SCOPE_EVIDENCE_ONLY = (
    "EVIDENCE_BUNDLE_DETERMINISTICALLY_VERIFIABLE; AI_PROSE_NOT_BIT_REPRODUCIBLE"
)


def serialize_evidence_bundle_payload(items: List[EvidenceItem]) -> List[Dict[str, Any]]:
    """The canonical projection of an Evidence Bundle — what is hashed into
    `evidence_bundle_hash`, what is sent to the provider, and what gets persisted, all one
    thing.

    This intentionally DELEGATES to the projection already used by the orchestration layer
    rather than re-declaring the field list a third time. A third independent copy could drift
    from the other two, and a drifted projection would silently break hash verification for
    every stored report — the exact failure mode `test_persisted_payload_hash_matches_
    compute_evidence_bundle_hash` exists to foreclose.
    """
    return _serialize_evidence_bundle(items)


def make_report_id(symbol: str, as_of: str) -> str:
    """`report_{symbol}_{as_of}_{uuid4}` — the id shape named in the proposal §8. The uuid
    suffix means two reports for the same symbol/as_of never collide, so the store's
    immutability rule can never be tripped by a legitimate regeneration."""
    return f"report_{symbol}_{as_of}_{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class ResearchAnalystReportIdentity:
    """Immutable identity + full provenance of one AI Research Analyst report.

    Fields 1-11 are exactly the proposal §8 design. Everything after `generated_at` is
    trailing-defaulted — the same backward-compatibility discipline used by
    `ResearchRunIdentity.signal_configuration_hash` (Phase 8A) and
    `ResearchResultManifest.schema_version` (Phase 9) — so a future field never invalidates an
    already-persisted identity file.
    """
    report_id: str
    symbol: str
    as_of: str                       # the PIT cutoff the ENTIRE report is anchored to
    research_run_id: Optional[str]   # Mode A only; None in Mode B — never fabricated
    evidence_bundle_hash: str        # compute_canonical_sha256 over the full Evidence Bundle
    data_snapshot_id: Optional[str]  # links to SnapshotManager where market/fundamental data
                                     # participates; None when no snapshot was involved
    model_version: str               # provider-reported model version, or NOT_REPORTED_BY_PROVIDER
    prompt_version: str              # versioned prompt/analyst-logic id — a future prompt change
                                     # never silently redefines an old report's meaning
    code_version: str                # get_code_version(), reused verbatim
    code_state: str
    generated_at: str                # wall-clock generation time — distinct from `as_of`

    # --- trailing-defaulted: provider provenance (CEO directive Step 5) --------------------
    provider_id: str = NOT_REPORTED_BY_PROVIDER      # which LLM provider produced the prose
    provider_version: str = NOT_REPORTED_BY_PROVIDER  # provider adapter version
    model: str = NOT_REPORTED_BY_PROVIDER             # the model as REQUESTED
    llm_request_id: str = NOT_REPORTED_BY_PROVIDER    # correlates back to the LLMRequest
    data_origin: str = NOT_REPORTED_BY_PROVIDER       # REAL_PROVIDER | SYNTHETIC_DATA
    schema_version: str = REPORT_IDENTITY_SCHEMA_VERSION
    reproducibility_scope: str = REPRODUCIBILITY_SCOPE_EVIDENCE_ONLY

    def __post_init__(self):
        for field_name in ("report_id", "symbol", "as_of", "evidence_bundle_hash",
                           "model_version", "prompt_version", "code_version", "code_state",
                           "generated_at"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"FAIL CLOSED: ResearchAnalystReportIdentity.{field_name} must be a "
                    "non-empty string."
                )
        # Optional means "genuinely absent", spelled None. An empty string would be a fabricated
        # link to a run/snapshot that does not exist — rejected rather than normalized away.
        for field_name in ("research_run_id", "data_snapshot_id"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(
                    f"FAIL CLOSED: ResearchAnalystReportIdentity.{field_name} must be either "
                    "None (genuinely absent) or a non-empty string — never an empty placeholder."
                )
        if self.reproducibility_scope != REPRODUCIBILITY_SCOPE_EVIDENCE_ONLY:
            raise ValueError(
                "FAIL CLOSED: ResearchAnalystReportIdentity.reproducibility_scope cannot be "
                f"overridden (got {self.reproducibility_scope!r}). This codebase verifies the "
                "Evidence Bundle deterministically and makes NO bit-level reproducibility claim "
                "about AI-generated prose; an identity is not permitted to assert otherwise."
            )


def build_research_analyst_report_identity(
    result: AIResearchOutputResult,
    symbol: str,
    as_of: str,
    research_run_id: Optional[str] = None,
    data_snapshot_id: Optional[str] = None,
    provider_version: Optional[str] = None,
    data_origin: Optional[str] = None,
    report_id: Optional[str] = None,
) -> ResearchAnalystReportIdentity:
    """Builds the identity from an already-validated `AIResearchOutputResult` — the only
    supported construction path for a real report, so provider provenance is copied from what
    the provider actually reported rather than re-typed by a caller.

    `provider_version` / `data_origin` are accepted as arguments because `AIResearchIdentity`
    does not carry them (they live on the provider object and on `LLMResponse` respectively);
    when a caller does not supply them they are recorded as NOT_REPORTED_BY_PROVIDER rather
    than guessed.
    """
    ai = result.identity
    code_version, code_state = get_code_version()
    return ResearchAnalystReportIdentity(
        report_id=report_id or make_report_id(symbol, as_of),
        symbol=symbol,
        as_of=as_of,
        research_run_id=research_run_id,
        evidence_bundle_hash=ai.evidence_bundle_hash,
        data_snapshot_id=data_snapshot_id,
        model_version=ai.model_version or NOT_REPORTED_BY_PROVIDER,
        prompt_version=ai.prompt_version,
        code_version=code_version,
        code_state=code_state,
        generated_at=ai.generated_at,
        provider_id=ai.provider_id,
        provider_version=provider_version or NOT_REPORTED_BY_PROVIDER,
        model=ai.model,
        llm_request_id=ai.request_id,
        data_origin=data_origin or NOT_REPORTED_BY_PROVIDER,
    )


def verify_report_evidence_integrity(
    identity: ResearchAnalystReportIdentity,
    evidence_payload: List[Dict[str, Any]],
) -> bool:
    """OPT-IN integrity check, mirroring `verify_result_manifest_integrity()`'s established
    pattern — never called automatically inside `ResearchAnalystReportStore.get_report()`.

    Recomputes the canonical hash of the persisted Evidence Bundle and compares it with the
    `evidence_bundle_hash` recorded at generation time, answering: "is the evidence stored
    alongside this report still exactly the evidence the AI was shown?" It says nothing
    whatsoever about the prose — see this module's docstring.
    """
    return compute_canonical_sha256(evidence_payload) == identity.evidence_bundle_hash
