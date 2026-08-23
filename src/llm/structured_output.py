"""
structured_output.py — Structured Research Output Contract & schema validation.

CEO Directive item 2: "LLM 不允许直接返回一大段无法验证的文字." Defines the exact 10-field
schema the directive specifies, and the LLM-response -> Contract parsing boundary — the same
shape as news_provider.py's `_parse_raw_item()`: an untrusted dict goes in, a validated
dataclass comes out, or the parse fails closed with a specific, actionable error.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

REQUIRED_STRUCTURED_OUTPUT_FIELDS = (
    "summary", "technical_analysis", "fundamental_analysis", "quant_analysis",
    "news_analysis", "bull_case", "bear_case", "risk_analysis", "conclusion", "evidence_ids",
)
NARRATIVE_TEXT_FIELDS = (
    "summary", "technical_analysis", "fundamental_analysis", "quant_analysis",
    "news_analysis", "bull_case", "bear_case", "risk_analysis", "conclusion",
)


@dataclass(frozen=True)
class StructuredResearchOutput:
    """AI Interpretation content. Explicitly NOT an EvidenceItem, cannot be converted into one —
    no function anywhere in src/llm/ performs that conversion (directive item 5: "AI
    Interpretation 可以作为最终报告内容，但不能重新成为 Evidence 输入")."""
    summary: str
    technical_analysis: str
    fundamental_analysis: str
    quant_analysis: str
    news_analysis: str
    bull_case: str
    bear_case: str
    risk_analysis: str
    conclusion: str
    evidence_ids: List[str]

    def __post_init__(self):
        for field_name in NARRATIVE_TEXT_FIELDS:
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"FAIL CLOSED: StructuredResearchOutput.{field_name} must be a non-empty string.")
        if not isinstance(self.evidence_ids, list) or not all(isinstance(e, str) for e in self.evidence_ids):
            raise ValueError("FAIL CLOSED: StructuredResearchOutput.evidence_ids must be a List[str].")
        if not self.evidence_ids:
            raise ValueError(
                "FAIL CLOSED: StructuredResearchOutput.evidence_ids must not be empty — a "
                "report must cite at least one evidence item; refusing to accept an "
                "uncited/unsupported report."
            )


def parse_structured_output(raw: Dict[str, Any]) -> StructuredResearchOutput:
    """The LLMResponse.raw_structured_output -> StructuredResearchOutput boundary. `raw` is
    untrusted (it is, structurally, "whatever JSON the model produced") — every field is
    checked before a StructuredResearchOutput is ever constructed. Never guesses a missing
    field's meaning, never fabricates a default value."""
    if not isinstance(raw, dict):
        raise ValueError(f"FAIL CLOSED: malformed structured output (expected dict, got {type(raw).__name__}).")
    if not raw:
        raise ValueError("FAIL CLOSED: empty structured output — provider returned no content.")

    missing = [f for f in REQUIRED_STRUCTURED_OUTPUT_FIELDS if f not in raw]
    if missing:
        raise ValueError(f"FAIL CLOSED: structured output missing required field(s) {missing}.")

    for field_name in NARRATIVE_TEXT_FIELDS:
        if not isinstance(raw[field_name], str):
            raise ValueError(
                f"FAIL CLOSED: wrong datatype for '{field_name}' (expected str, got "
                f"{type(raw[field_name]).__name__})."
            )
    if not isinstance(raw["evidence_ids"], list):
        raise ValueError(
            f"FAIL CLOSED: wrong datatype for 'evidence_ids' (expected list, got "
            f"{type(raw['evidence_ids']).__name__})."
        )

    return StructuredResearchOutput(
        summary=raw["summary"], technical_analysis=raw["technical_analysis"],
        fundamental_analysis=raw["fundamental_analysis"], quant_analysis=raw["quant_analysis"],
        news_analysis=raw["news_analysis"], bull_case=raw["bull_case"], bear_case=raw["bear_case"],
        risk_analysis=raw["risk_analysis"], conclusion=raw["conclusion"],
        evidence_ids=list(raw["evidence_ids"]),
    )
