"""
research_analyst.py — Research Analyst orchestration: Evidence Bundle -> LLM Provider ->
Structured Output -> Deterministic Validator -> Validated AI Research Output.

CEO Directive "LLM Provider Architecture & Implementation". This module is the ONLY caller of
`LLMProvider.generate_structured_research()` in this codebase — the Evidence Boundary (directive
item 3) is enforced here structurally: this function's only inputs are an already-assembled,
already-validated `List[EvidenceItem]` and an `LLMProvider` instance; it has no database handle,
no News/Market API client, and no search capability to hand to the provider even if it wanted to.

Explicit scope boundary: this function stops at a VALIDATED STRUCTURED OUTPUT — it does not
render a Markdown/UI report, does not persist anything to ResearchRunStore, and does not build
the full 10-section narrative "Research Report" described in
AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §7-§9. Those remain future, separately-
authorized work, per this directive's explicit "不要继续完整 Research Analyst Report" instruction.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.quant.evidence.evidence_item import EvidenceItem, compute_evidence_bundle_hash
from src.llm.provider_base import LLMProvider, LLMRequest, LLMTokenUsage
from src.llm.structured_output import StructuredResearchOutput, parse_structured_output
from src.llm.citation_validator import validate_citations


@dataclass(frozen=True)
class AIResearchIdentity:
    """Directive item 8: "Research identity 至少记录: provider, model, model version, request
    configuration, evidence bundle hash." Deliberately contains NOTHING that implies the AI's
    prose is bit-reproducible — see this class's own docstring note below, not just a comment
    buried elsewhere. Evidence reproducibility (evidence_bundle_hash is independently
    re-verifiable) is a categorically different guarantee from LLM wording reproducibility
    (not claimed anywhere in this codebase, for this or any prior AI-adjacent design)."""
    request_id: str
    provider_id: str
    model: str
    model_version: Optional[str]
    prompt_version: str
    evidence_bundle_hash: str
    timeout_seconds: float
    generated_at: str
    token_usage: LLMTokenUsage


@dataclass(frozen=True)
class AIResearchOutputResult:
    identity: AIResearchIdentity
    output: StructuredResearchOutput


def _serialize_evidence_bundle(evidence_bundle: List[EvidenceItem]) -> List[Dict[str, Any]]:
    """Same field projection used by compute_evidence_bundle_hash() — what gets sent to the
    provider and what gets hashed are the same canonical view, by construction, not by
    coincidence-prone duplication."""
    return [
        {
            "evidence_id": i.evidence_id, "category": i.category, "kind": i.kind,
            "content": i.content, "event_date": i.event_date, "source": i.source,
            "data_origin": i.data_origin,
        }
        for i in evidence_bundle
    ]


def generate_ai_research_output(
    evidence_bundle: List[EvidenceItem],
    provider: LLMProvider,
    model: str,
    prompt_version: str = "1.0",
    timeout_seconds: float = 60.0,
    request_id: Optional[str] = None,
) -> AIResearchOutputResult:
    """Raises (never returns a partial/guessed result) on any failure:
    - ValueError("FAIL CLOSED: ...") for an empty evidence bundle, a request/response request_id
      mismatch, malformed/empty/schema-invalid structured output, or a citation validation
      failure (unknown evidence_id, unsupported number).
    - LLMProviderError (see provider_base.py) for any provider-level failure (timeout, auth,
      rate limit, provider unavailable) — propagated unmodified, never swallowed."""
    if not evidence_bundle:
        raise ValueError("FAIL CLOSED: cannot generate AI research output from an empty evidence bundle.")

    bundle_hash = compute_evidence_bundle_hash(evidence_bundle)
    payload = _serialize_evidence_bundle(evidence_bundle)
    req_id = request_id or f"req_{uuid.uuid4().hex}"

    request = LLMRequest(
        request_id=req_id, model=model, prompt_version=prompt_version,
        evidence_bundle_hash=bundle_hash, evidence_payload=payload,
        timeout_seconds=timeout_seconds,
    )

    # The ONLY call to the provider — everything before this line assembles the request from
    # already-validated Evidence; everything after this line only ever reads response.* fields.
    response = provider.generate_structured_research(request)

    if response.request_id != request.request_id:
        raise ValueError(
            f"FAIL CLOSED: provider response request_id '{response.request_id}' does not match "
            f"the request it was supposedly answering ('{request.request_id}')."
        )

    output = parse_structured_output(response.raw_structured_output)

    is_valid, errors = validate_citations(output, evidence_bundle)
    if not is_valid:
        raise ValueError(f"FAIL CLOSED: citation validation failed: {errors}")

    identity = AIResearchIdentity(
        request_id=req_id, provider_id=response.provider_id, model=response.model,
        model_version=response.model_version, prompt_version=prompt_version,
        evidence_bundle_hash=bundle_hash, timeout_seconds=timeout_seconds,
        generated_at=response.received_at.isoformat(), token_usage=response.token_usage,
    )
    return AIResearchOutputResult(identity=identity, output=output)
