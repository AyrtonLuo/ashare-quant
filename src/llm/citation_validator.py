"""
citation_validator.py — Deterministic Citation / Numeric-Hallucination Validator.

CEO Directive item 4: every evidence_id, number, and key fact in the LLM's output must trace
back to Evidence. Validation failure is FAIL CLOSED — never auto-corrected, never guessed.
This is code, not a second LLM call — the directive's own "Deterministic Validator" stage.

Known, disclosed limitation (not hidden): this validator mechanically verifies (a) every cited
evidence_id actually exists in the bundle that was sent, and (b) every number appearing in the
narrative text is traceable (within tolerance) to a number present in the content of a cited
evidence item. It does NOT perform semantic verification of arbitrary prose claims ("关键事实")
beyond what the numeric scan and evidence_id citation presence together provide — full semantic
fact-checking of free text is not deterministic and is explicitly out of scope for this phase.
"""

import re
from typing import Any, List, Set, Tuple

from src.quant.evidence.evidence_item import EvidenceItem
from src.llm.structured_output import StructuredResearchOutput, NARRATIVE_TEXT_FIELDS

_NUMBER_PATTERN = re.compile(r"-?\d+\.?\d*")
_NUMBER_TOLERANCE = 0.01


def _extract_numbers_from_text(text: str) -> List[float]:
    numbers = []
    for match in _NUMBER_PATTERN.finditer(text):
        token = match.group()
        if token in ("", "-", "."):
            continue
        try:
            numbers.append(float(token))
        except ValueError:
            continue
    return numbers


def _extract_numbers_from_value(value: Any, acc: Set[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        acc.add(round(float(value), 6))
    elif isinstance(value, dict):
        for v in value.values():
            _extract_numbers_from_value(v, acc)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _extract_numbers_from_value(v, acc)


def _number_is_supported(n: float, supported: Set[float]) -> bool:
    return any(abs(n - s) <= _NUMBER_TOLERANCE for s in supported)


def validate_citations(
    output: StructuredResearchOutput, evidence_bundle: List[EvidenceItem],
) -> Tuple[bool, List[str]]:
    """`evidence_bundle` must be the EXACT bundle that was actually sent to the LLM for this
    request (not some larger universe of evidence that happens to exist elsewhere in the
    system) — citing an id that exists elsewhere but wasn't part of THIS request's bundle is
    exactly the "unsupported evidence" failure this function is designed to catch."""
    errors: List[str] = []
    bundle_ids = {e.evidence_id for e in evidence_bundle}

    unknown_ids = [eid for eid in output.evidence_ids if eid not in bundle_ids]
    if unknown_ids:
        errors.append(
            f"evidence_ids references id(s) not present in the evidence bundle actually sent "
            f"for this request: {unknown_ids}"
        )

    cited_items = [e for e in evidence_bundle if e.evidence_id in output.evidence_ids]
    supported_numbers: Set[float] = set()
    for item in cited_items:
        _extract_numbers_from_value(item.content, supported_numbers)

    narrative_text = " ".join(getattr(output, f) for f in NARRATIVE_TEXT_FIELDS)
    narrative_numbers = _extract_numbers_from_text(narrative_text)
    unsupported_numbers = sorted({
        n for n in narrative_numbers if not _number_is_supported(n, supported_numbers)
    })
    if unsupported_numbers:
        errors.append(
            f"narrative text contains number(s) not traceable to any cited evidence item's "
            f"content: {unsupported_numbers}"
        )

    return len(errors) == 0, errors
