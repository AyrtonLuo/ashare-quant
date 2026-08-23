"""
report.py — Research Report Generation Layer (AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md
§7): the full 10-section report, assembled deterministically around a validated
`StructuredResearchOutput`.

How the 10 sections of §7 map onto what already exists — no schema change was needed
=====================================================================================
`StructuredResearchOutput` (shipped in `33296e7`) carries exactly 9 narrative fields plus
`evidence_ids`. §7 specifies 10 sections, of which section 9 (Data Confidence) is **Model Output
only — a computed metric, never AI-authored**. So the nine AI sections map 1:1 onto the nine
narrative fields, and section 9 is produced here by `compute_data_confidence()`. The report layer
therefore required no modification to the LLM contract, and none was made.

Guarantees, each enforced structurally rather than by prompt wording or convention
==================================================================================
- **Every fact and number traces to Evidence.** `generate_ai_research_output()` already runs the
  deterministic citation validator and fails closed; this layer never relaxes, retries, or
  works around that. Per-section evidence attribution is then *derived* by the same numeric
  tracing logic (see `derive_section_evidence_ids()` and its disclosed limitation).
- **AI interpretation never becomes Evidence.** Nothing in this module constructs an
  `EvidenceItem`. The Evidence Bundle is an input, fixed before generation; report prose flows
  strictly one way, out.
- **Nothing is fabricated.** A report section whose evidence category is absent from the bundle
  is rendered as an explicit NOT AVAILABLE marker — never estimated, never quietly omitted. The
  AI's prose for such a section is preserved verbatim on `suppressed_ai_body` rather than
  discarded, matching this project's "declare, never silently discard" rule.
- **No single Buy/Sell verdict — by construction.** There is no verdict, rating, signal, or
  score-of-the-stock field anywhere on `ResearchReport`; there is nowhere for one to live. Bull
  Case and Bear Case are both mandatory sections, and a report whose Bull and Bear text are
  identical (a degenerate way to fake balance) fails closed.
- **Data Confidence is computed, never self-rated** — see data_confidence.py.
- **AI prose is not bit-reproducible, and nothing here claims it is.** The report carries the
  `ResearchAnalystReportIdentity` whose `reproducibility_scope` states the honest boundary; the
  Evidence Bundle is hash-verifiable, the wording is not.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Set, Tuple

from src.llm.citation_validator import (
    _extract_numbers_from_text,
    _extract_numbers_from_value,
    _number_is_supported,
)
from src.llm.provider_base import LLMProvider
from src.llm.research_analyst import generate_ai_research_output
from src.llm.structured_output import StructuredResearchOutput
from src.quant.evidence.evidence_item import EvidenceItem
from src.quant.research_report.data_confidence import (
    CONFLICT_DETECTION_SCOPE,
    DataConfidence,
    EvidenceConflict,
    compute_data_confidence,
    detect_evidence_conflicts,
)
from src.quant.research_report.report_identity import (
    ResearchAnalystReportIdentity,
    build_research_analyst_report_identity,
    serialize_evidence_bundle_payload,
)
from src.quant.research_report.report_store import ResearchAnalystReportStore

CONTENT_TYPE_FACT = "FACT"
CONTENT_TYPE_MODEL_OUTPUT = "MODEL_OUTPUT"
CONTENT_TYPE_AI = "AI_INTERPRETATION"

NOT_INVESTMENT_ADVICE_DISCLAIMER = (
    "This is a research artifact, not investment advice. It contains no buy/sell recommendation "
    "and no single verdict by construction — Bull Case and Bear Case are both mandatory. "
    "Historical and point-in-time data are research inputs and do not guarantee future results."
)

REPORT_LIMITATIONS: Tuple[str, ...] = (
    "AI-authored prose is NOT bit-reproducible: regenerating this report from the same "
    "evidence_bundle_hash may legitimately produce different wording. Only the Evidence Bundle "
    "is deterministically verifiable.",
    "Citation validation is a deterministic evidence-id and numeric-traceability scan, not full "
    "semantic fact-checking of free text.",
    f"Conflict detection scope: {CONFLICT_DETECTION_SCOPE}.",
    "Per-section evidence attribution is DERIVED from numeric tracing, not asserted per-section "
    "by the model — StructuredResearchOutput carries one report-level citation list.",
    "Category-level historical eligibility (proposal §3.4 historical_eligible) is NOT implemented "
    "anywhere in this codebase; absent categories are reported as NOT AVAILABLE without "
    "distinguishing 'structurally current-only' from 'simply absent'.",
)


def _not_available_marker(category: str) -> str:
    return (
        f"NOT AVAILABLE — the Evidence Bundle for this as_of contains no {category} evidence. "
        "This section is deliberately left unpopulated rather than estimated, approximated, or "
        "backfilled."
    )


@dataclass(frozen=True)
class ReportSection:
    """One of the ten §7 sections. `content_type` makes the Fact / Model Output / AI
    Interpretation distinction visible on the artifact itself, not just internally."""
    number: int
    title: str
    content_type: str
    body: str
    evidence_ids: Tuple[str, ...]
    is_missing_data: bool = False
    suppressed_ai_body: Optional[str] = None  # AI text withheld because its category had no
                                              # evidence — kept, never silently discarded


@dataclass(frozen=True)
class ResearchReport:
    """The complete artifact. Deliberately carries NO verdict/rating/recommendation field."""
    identity: ResearchAnalystReportIdentity
    sections: Tuple[ReportSection, ...]
    data_confidence: DataConfidence
    conflicts: Tuple[EvidenceConflict, ...]
    output: StructuredResearchOutput
    evidence_bundle: Tuple[EvidenceItem, ...]
    disclaimer: str = NOT_INVESTMENT_ADVICE_DISCLAIMER
    limitations: Tuple[str, ...] = REPORT_LIMITATIONS

    @property
    def section_by_number(self) -> Dict[int, ReportSection]:
        return {s.number: s for s in self.sections}


# Section number -> (title, content_type, StructuredResearchOutput field, required evidence
# categories). `None` for the field means the section is not AI-authored; an empty category
# tuple means the section synthesizes the whole bundle and can never be "missing".
_SECTION_SPEC: Tuple[Tuple[int, str, str, Optional[str], Tuple[str, ...]], ...] = (
    (1, "Executive Summary", CONTENT_TYPE_AI, "summary", ()),
    (2, "Technical Analysis", CONTENT_TYPE_MODEL_OUTPUT + "+" + CONTENT_TYPE_AI,
     "technical_analysis", ("TECHNICAL",)),
    (3, "Fundamental Analysis", CONTENT_TYPE_FACT + "+" + CONTENT_TYPE_AI,
     "fundamental_analysis", ("FUNDAMENTAL",)),
    (4, "Quant Factor Analysis", CONTENT_TYPE_MODEL_OUTPUT + "+" + CONTENT_TYPE_AI,
     "quant_analysis", ("QUANT_FACTOR",)),
    (5, "News / Event Analysis", CONTENT_TYPE_FACT + "+" + CONTENT_TYPE_AI,
     "news_analysis", ("NEWS", "ANNOUNCEMENT")),
    (6, "Bull Case", CONTENT_TYPE_AI, "bull_case", ()),
    (7, "Bear Case", CONTENT_TYPE_AI, "bear_case", ()),
    (8, "Risk Analysis", CONTENT_TYPE_FACT + "+" + CONTENT_TYPE_MODEL_OUTPUT + "+" + CONTENT_TYPE_AI,
     "risk_analysis", ()),
    (9, "Data Confidence", CONTENT_TYPE_MODEL_OUTPUT, None, ()),
    (10, "Final Research Conclusion", CONTENT_TYPE_AI, "conclusion", ()),
)


def derive_section_evidence_ids(
    section_text: str, cited_items: Sequence[EvidenceItem],
) -> Tuple[str, ...]:
    """Which cited evidence items actually back this section's numbers.

    Deliberately reuses the citation validator's own number-extraction and tolerance rather than
    declaring a second, subtly-different numeric scanner that could disagree with the validator
    that gates the report.

    Disclosed limitation: `StructuredResearchOutput` carries ONE report-level `evidence_ids`
    list, so section-level attribution is *derived* here, not asserted by the model. A section
    containing no numbers yields an empty tuple — that means "no numeric claim to attribute",
    never "unsupported".
    """
    numbers = _extract_numbers_from_text(section_text)
    if not numbers:
        return ()
    attributed = []
    for item in cited_items:
        supported: Set[float] = set()
        _extract_numbers_from_value(item.content, supported)
        if any(_number_is_supported(n, supported) for n in numbers):
            attributed.append(item.evidence_id)
    return tuple(sorted(set(attributed)))


def _risk_addendum(
    conflicts: Sequence[EvidenceConflict], confidence: DataConfidence,
) -> str:
    """Code-generated, explicitly labelled MODEL_OUTPUT text appended to §7 #8. Unresolved
    conflicts and absent categories are surfaced by deterministic code so they can never be
    softened, omitted, or resolved by the narrative."""
    lines = ["", "--- DETERMINISTIC RISK ADDENDUM (code-generated, not AI-authored) ---"]
    if conflicts:
        lines.append(f"UNRESOLVED EVIDENCE CONFLICTS: {len(conflicts)} (none resolved — both "
                     "sides are retained and cited):")
        for c in conflicts:
            lines.append(f"  - {c.key_repr} on {c.event_date}: {', '.join(c.evidence_ids)} "
                         f"[{c.detection}]")
    else:
        lines.append(
            "UNRESOLVED EVIDENCE CONFLICTS: 0 detected. Detection scope: "
            f"{CONFLICT_DETECTION_SCOPE}."
        )
    if confidence.missing_categories:
        lines.append(
            "MISSING EVIDENCE CATEGORIES (reported, never estimated): "
            + ", ".join(confidence.missing_categories)
        )
    else:
        lines.append("MISSING EVIDENCE CATEGORIES: none.")
    return "\n".join(lines)


def _data_confidence_body(confidence: DataConfidence) -> str:
    parts = [
        f"Data Confidence: {confidence.score} ({confidence.band}) — computed by "
        f"{confidence.computed_by}, never self-rated by the model.",
        f"Evidence items: {confidence.evidence_count} "
        f"(FACT={confidence.fact_count}, MODEL_OUTPUT={confidence.model_output_count}).",
        f"Provenance: real_provider_ratio={confidence.real_provider_ratio}, "
        f"breakdown={confidence.origin_breakdown}.",
        f"Category coverage: present={list(confidence.present_categories)}, "
        f"missing={list(confidence.missing_categories)}.",
        f"Recency: {confidence.dated_evidence_count} dated item(s), "
        f"median age={confidence.median_evidence_age_days} day(s), "
        f"oldest={confidence.oldest_evidence_age_days} day(s).",
        f"Unresolved conflicts: {confidence.unresolved_conflict_count}.",
        f"Sub-scores: {confidence.components}.",
    ]
    return "\n".join(parts)


def assemble_report_sections(
    output: StructuredResearchOutput,
    evidence_bundle: Sequence[EvidenceItem],
    confidence: DataConfidence,
    conflicts: Sequence[EvidenceConflict],
) -> Tuple[ReportSection, ...]:
    """Builds all ten sections. Pure and deterministic given its inputs — it performs no LLM
    call of its own."""
    present_by_category = {item.category for item in evidence_bundle}
    cited_items = [e for e in evidence_bundle if e.evidence_id in set(output.evidence_ids)]

    sections: List[ReportSection] = []
    for number, title, content_type, field_name, categories in _SECTION_SPEC:
        if field_name is None:
            sections.append(ReportSection(
                number=number, title=title, content_type=content_type,
                body=_data_confidence_body(confidence), evidence_ids=(),
            ))
            continue

        ai_body = getattr(output, field_name)
        has_evidence = (not categories) or any(c in present_by_category for c in categories)

        if not has_evidence:
            sections.append(ReportSection(
                number=number, title=title, content_type=content_type,
                body=_not_available_marker("/".join(categories)), evidence_ids=(),
                is_missing_data=True, suppressed_ai_body=ai_body,
            ))
            continue

        body = (ai_body + _risk_addendum(conflicts, confidence)) if number == 8 else ai_body
        sections.append(ReportSection(
            number=number, title=title, content_type=content_type, body=body,
            evidence_ids=derive_section_evidence_ids(ai_body, cited_items),
        ))
    return tuple(sections)


def generate_research_report(
    evidence_bundle: List[EvidenceItem],
    provider: LLMProvider,
    symbol: str,
    as_of: datetime,
    model: str,
    prompt_version: str = "1.0",
    research_run_id: Optional[str] = None,
    data_snapshot_id: Optional[str] = None,
    provider_version: Optional[str] = None,
    data_origin: Optional[str] = None,
) -> ResearchReport:
    """The one entry point: Evidence Bundle -> validated AI output -> deterministic Data
    Confidence and conflict detection -> identity -> the 10-section report.

    Fails closed, never partially, on: an empty Evidence Bundle, any provider-level failure,
    malformed/schema-invalid structured output, citation-validation failure (all four inherited
    unmodified from `generate_ai_research_output()`), and on a degenerate Bull/Bear pair.
    """
    if not evidence_bundle:
        raise ValueError(
            "FAIL CLOSED: cannot generate a Research Report from an empty Evidence Bundle."
        )

    result = generate_ai_research_output(
        evidence_bundle, provider, model=model, prompt_version=prompt_version,
    )
    output = result.output

    # Bull and Bear are already mandatory non-empty strings (schema). Identical text would
    # satisfy the schema while defeating the entire reason both are mandatory.
    if output.bull_case.strip() == output.bear_case.strip():
        raise ValueError(
            "FAIL CLOSED: Bull Case and Bear Case are identical — a report must present two "
            "genuinely distinct cases, never one verdict duplicated into both sections."
        )

    conflicts = detect_evidence_conflicts(evidence_bundle)
    confidence = compute_data_confidence(evidence_bundle, as_of, conflicts=conflicts)

    identity = build_research_analyst_report_identity(
        result, symbol=symbol, as_of=as_of.strftime("%Y-%m-%d"),
        research_run_id=research_run_id, data_snapshot_id=data_snapshot_id,
        provider_version=provider_version, data_origin=data_origin,
    )

    return ResearchReport(
        identity=identity,
        sections=assemble_report_sections(output, evidence_bundle, confidence, conflicts),
        data_confidence=confidence,
        conflicts=tuple(conflicts),
        output=output,
        evidence_bundle=tuple(evidence_bundle),
    )


def persist_research_report(
    store: ResearchAnalystReportStore, report: ResearchReport,
) -> str:
    """Persists through the existing Step 5 store — the identity, the validated output, and the
    Evidence Bundle that was hashed into it. No new persistence format is introduced."""
    return store.create_report(
        report.identity, report.output,
        serialize_evidence_bundle_payload(list(report.evidence_bundle)),
    )


def render_report_markdown(report: ResearchReport) -> str:
    """Plain-Markdown rendering. Deliberately framework-free — no Streamlit import lives here or
    anywhere outside `src/app/streamlit_app.py`."""
    identity = report.identity
    lines = [
        f"# Research Report — {identity.symbol} (as of {identity.as_of})",
        "",
        f"> {report.disclaimer}",
        "",
        "## Provenance",
        f"- report_id: `{identity.report_id}`",
        f"- evidence_bundle_hash: `{identity.evidence_bundle_hash}`",
        f"- provider / model / model_version: `{identity.provider_id}` / `{identity.model}` / "
        f"`{identity.model_version}`",
        f"- prompt_version: `{identity.prompt_version}`",
        f"- code_version: `{identity.code_version}` ({identity.code_state})",
        f"- research_run_id: `{identity.research_run_id}`",
        f"- reproducibility_scope: `{identity.reproducibility_scope}`",
        "",
    ]
    for section in report.sections:
        lines.append(f"## {section.number}. {section.title}  `[{section.content_type}]`")
        if section.is_missing_data:
            lines.append("**MISSING DATA**")
        lines.append("")
        lines.append(section.body)
        if section.evidence_ids:
            lines.append("")
            lines.append(f"_Evidence: {', '.join(section.evidence_ids)}_")
        if section.suppressed_ai_body is not None:
            lines.append("")
            lines.append(
                "_AI text withheld for this section because its evidence category was absent "
                f"(retained, not discarded): {section.suppressed_ai_body}_"
            )
        lines.append("")

    lines.append("## Limitations")
    lines.extend(f"- {limitation}" for limitation in report.limitations)
    return "\n".join(lines)
