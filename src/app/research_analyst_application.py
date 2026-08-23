"""
research_analyst_application.py — Application Layer for the AI Research Analyst
(AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §9, §11 step 6).

Mirrors `research_application.py`'s contract exactly: the UI calls only this module, this module
imports no UI framework, and every value the UI renders is produced here from certified data or
from an already-persisted artifact. `streamlit_app.py` remains the only file in the repository
permitted to import Streamlit; nothing here imports it, and nothing here renders.

Availability, stated up front rather than discovered by a reader
================================================================
A real LLM provider now exists (`src/llm/openai_provider.py`, stdlib HTTP, no vendor SDK), so
this module reports availability from the credential preflight: `LLM_PROVIDER_AVAILABLE` when
`OPENAI_API_KEY` is present, `LLM_PROVIDER_CREDENTIALS_UNAVAILABLE` when it is not.

`generate_analyst_report()` uses the real provider whenever the credential is present, and
**fails closed when it is not**. A caller may still opt in to a clearly-labelled synthetic
narrative (`allow_synthetic_narrative=True`) — used when no credential is configured, or to
exercise the rendering path without spending tokens — which is:
  * assembled from the SAME real, certified, PIT-filtered Evidence Bundle as any other report —
    every fact and number on the page is real GOLDEN_DATASET evidence;
  * accompanied by placeholder prose that says so in every single section, authored here and not
    by any model, so it can never be mistaken for analysis;
  * tagged `data_origin="SYNTHETIC_DATA"` on the persisted identity and surfaced as
    `narrative_origin` on the view, so the UI badges it exactly the way the workbench already
    badges `LIVE PROVIDER: NOT VERIFIED`.
This mirrors an existing, established convention in this codebase — `LiveNewsAnnouncementProvider`
refuses explicitly while `SyntheticNewsAnnouncementProvider` serves labelled fixtures — rather
than inventing a new one.

Evidence availability is likewise reported, never faked: the certified workbench dataset carries
MARKET, FUNDAMENTAL and (computed from those same prices) TECHNICAL evidence. It carries no news
feed, no factor-evidence assembly function and no risk-evidence assembly function, so NEWS,
QUANT_FACTOR and RISK are reported NOT AVAILABLE with a reason. They are never approximated.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from src.app.golden_dataset_seed import (
    DATA_ORIGIN as GOLDEN_DATA_ORIGIN,
    SYMBOL_DISPLAY_NAMES,
    fundamental_data as golden_fundamental_data,
    market_data as golden_market_data,
)
from src.llm.credential import LLMProviderCredentialPreflight
from src.llm.fake_provider import FakeLLMProvider
from src.llm.openai_provider import (
    OPENAI_API_KEY_ENV_VAR,
    OPENAI_PROVIDER_ID,
    OpenAILLMProvider,
)
from src.llm.provider_base import LLMProvider, LLMProviderError
from src.quant.evidence.evidence_item import (
    EvidenceItem,
    assemble_fundamental_evidence,
    assemble_market_evidence,
    assemble_technical_evidence,
    compute_evidence_bundle_hash,
)
from src.quant.research_report.data_confidence import (
    REPORT_EVIDENCE_CATEGORIES,
    compute_data_confidence,
    detect_evidence_conflicts,
)
from src.quant.research_report.report import (
    ResearchReport,
    assemble_report_sections,
    generate_research_report,
    persist_research_report,
    render_report_markdown,
)
from src.quant.research_report.report_identity import (
    ResearchAnalystReportIdentity,
    verify_report_evidence_integrity,
)
from src.quant.research_report.report_store import ResearchAnalystReportStore
from src.quant.technical.indicators import (
    compute_macd,
    compute_moving_average,
    compute_rsi,
)

REPORT_STORE_BASE_DIR = "data/research/analyst_reports"

# Only `openai` has a concrete implementation; the other two are listed so the UI can show the
# preflight for a credential a future provider would use. A key for a vendor with no
# implementation never makes that vendor usable.
KNOWN_LLM_PROVIDERS: Tuple[Tuple[str, str], ...] = (
    (OPENAI_PROVIDER_ID, OPENAI_API_KEY_ENV_VAR),
    ("anthropic", "ANTHROPIC_API_KEY"),
    ("gemini", "GEMINI_API_KEY"),
)

DEFAULT_LLM_MODEL = "gpt-4o-mini"
LLM_AVAILABLE_STATUS = "LLM_PROVIDER_AVAILABLE"
LLM_CREDENTIALS_UNAVAILABLE_STATUS = "LLM_PROVIDER_CREDENTIALS_UNAVAILABLE"
NARRATIVE_ORIGIN_SYNTHETIC = "SYNTHETIC_DATA"
SYNTHETIC_NARRATIVE_WARNING = (
    "SYNTHETIC NARRATIVE — no LLM API was called. The Evidence Bundle below is real, certified, "
    "PIT-filtered data; the prose is a fixed placeholder authored by the application layer, not "
    "analysis. Do not read it as a view on this security."
)

# Why a category can be absent. Stated per category rather than left to the reader to infer.
_CATEGORY_UNAVAILABLE_REASONS: Dict[str, str] = {
    "NEWS": "The certified workbench dataset contains no news/announcement feed, and no "
            "persistent NewsAnnouncementStore exists in this codebase.",
    "QUANT_FACTOR": "No factor-evidence assembly function exists; factor outputs live in "
                    "certified research runs and are not exposed as Evidence.",
    "RISK": "No risk-evidence assembly function exists; risk metrics live on BacktestResult "
            "inside certified research runs.",
    "MARKET": "No market evidence passed validation and the PIT cutoff for this as_of.",
    "FUNDAMENTAL": "No fundamental record was PIT-visible at this as_of.",
    "TECHNICAL": "Insufficient price history at this as_of for any indicator to satisfy its "
                 "warm-up window.",
}

ANALYST_LIMITATIONS: Tuple[str, ...] = (
    "A real LLM provider is implemented (OpenAI over stdlib HTTP, no vendor SDK). When no "
    "credential is configured, report generation fails closed or produces an explicitly-"
    "labelled synthetic placeholder — never an unlabelled substitute.",
    "All evidence originates from the certified GOLDEN_DATASET; none of it is REAL_PROVIDER "
    "sourced (LIVE_PROVIDER_CREDENTIALS_UNAVAILABLE).",
    "Technical indicators here are computed on RAW golden closes (input_price_basis='RAW'); "
    "they are not corporate-action adjusted.",
    "AI-authored prose is never bit-reproducible; only the Evidence Bundle is hash-verifiable.",
)


class ResearchAnalystError(Exception):
    """Wraps any failure from the analyst pipeline for UI display. Never swallows a failure and
    never substitutes a default — the original FAIL CLOSED message is preserved."""


# --- Views (plain data the UI renders; no framework types) ---------------------------------------

@dataclass(frozen=True)
class LLMProviderStatusView:
    live_provider_implemented: bool
    status: str
    message: str
    credential_reports: Tuple[Dict[str, Any], ...]


@dataclass(frozen=True)
class EvidenceCategoryView:
    category: str
    available: bool
    item_count: int
    reason: Optional[str]
    data_origins: Tuple[str, ...]


@dataclass(frozen=True)
class EvidenceItemView:
    evidence_id: str
    category: str
    kind: str
    content: Any
    event_date: Optional[str]
    source: str
    data_origin: str


@dataclass(frozen=True)
class EvidenceBundleView:
    symbol: str
    as_of: str
    evidence_bundle_hash: str
    item_count: int
    items: Tuple[EvidenceItemView, ...]
    categories: Tuple[EvidenceCategoryView, ...]
    data_origin_breakdown: Dict[str, int]


@dataclass(frozen=True)
class DataConfidenceView:
    score: float
    band: str
    computed_by: str
    components: Dict[str, float]
    real_provider_ratio: float
    origin_breakdown: Dict[str, int]
    present_categories: Tuple[str, ...]
    missing_categories: Tuple[str, ...]
    fact_count: int
    model_output_count: int
    median_evidence_age_days: Optional[int]
    unresolved_conflict_count: int
    conflict_detection_scope: str


@dataclass(frozen=True)
class ReportSectionView:
    number: int
    title: str
    content_type: str
    body: str
    evidence_ids: Tuple[str, ...]
    is_missing_data: bool
    suppressed_ai_body: Optional[str]


@dataclass(frozen=True)
class ConflictView:
    category: str
    event_date: Optional[str]
    key_repr: str
    evidence_ids: Tuple[str, ...]
    detection: str


@dataclass(frozen=True)
class AnalystReportView:
    report_id: str
    symbol: str
    as_of: str
    generated_at: str
    provider_id: str
    model: str
    model_version: str
    prompt_version: str
    evidence_bundle_hash: str
    code_version: str
    code_state: str
    research_run_id: Optional[str]
    reproducibility_scope: str
    narrative_origin: str
    narrative_warning: Optional[str]
    sections: Tuple[ReportSectionView, ...]
    data_confidence: DataConfidenceView
    conflicts: Tuple[ConflictView, ...]
    evidence: EvidenceBundleView
    evidence_integrity_verified: bool
    disclaimer: str
    limitations: Tuple[str, ...]
    markdown: str


@dataclass(frozen=True)
class AnalystReportSummaryView:
    report_id: str
    symbol: str
    as_of: str
    generated_at: str
    narrative_origin: str


# --- Store / selectors -----------------------------------------------------------------------------

_report_store: Optional[ResearchAnalystReportStore] = None


def get_report_store() -> ResearchAnalystReportStore:
    global _report_store
    if _report_store is None:
        _report_store = ResearchAnalystReportStore(base_dir=REPORT_STORE_BASE_DIR)
    return _report_store


def reset_report_store(base_dir: Optional[str] = None) -> None:
    """Test-only escape hatch, mirroring research_application.reset_workbench_context()."""
    global _report_store
    _report_store = ResearchAnalystReportStore(base_dir=base_dir) if base_dir else None


def get_analyst_symbols() -> List[Dict[str, str]]:
    return [{"symbol": s, "display_name": n} for s, n in sorted(SYMBOL_DISPLAY_NAMES.items())]


def _openai_credential_available() -> bool:
    report = LLMProviderCredentialPreflight.inspect_credentials(
        OPENAI_PROVIDER_ID, OPENAI_API_KEY_ENV_VAR
    )
    return report["credential_status"] == "PRESENT_UNVERIFIED"


def get_llm_provider_status() -> LLMProviderStatusView:
    """Reports the preflight for every known provider. Only `openai` has an implementation, so
    only its credential can make generation possible; a key for an unimplemented vendor is shown
    but never treated as a capability."""
    reports = tuple(
        LLMProviderCredentialPreflight.inspect_credentials(provider_id, env_var)
        for provider_id, env_var in KNOWN_LLM_PROVIDERS
    )
    available = _openai_credential_available()
    return LLMProviderStatusView(
        live_provider_implemented=True,
        status=LLM_AVAILABLE_STATUS if available else LLM_CREDENTIALS_UNAVAILABLE_STATUS,
        message=(
            f"Real provider `{OPENAI_PROVIDER_ID}` is implemented (stdlib HTTP, no vendor SDK) "
            "and its credential is present. Structural presence only — no connectivity probe "
            "was made, so a call can still fail on quota, rate limit or network."
            if available else
            f"Real provider `{OPENAI_PROVIDER_ID}` is implemented, but {OPENAI_API_KEY_ENV_VAR} "
            "is not set. Report generation fails closed unless a synthetic, clearly-labelled "
            "narrative is explicitly requested."
        ),
        credential_reports=reports,
    )


# --- Evidence assembly -------------------------------------------------------------------------------

def _as_of_datetime(as_of: Any) -> datetime:
    if isinstance(as_of, datetime):
        return as_of
    if isinstance(as_of, date):
        return datetime(as_of.year, as_of.month, as_of.day)
    if isinstance(as_of, str):
        return datetime.fromisoformat(as_of)
    raise ResearchAnalystError(f"FAIL CLOSED: unsupported as_of type {type(as_of).__name__}.")


def _market_contracts_for(symbol: str, as_of: datetime) -> List[Any]:
    """PIT by construction: only bars whose trading_date is on or before the cutoff. This is the
    same one-rule-not-two-code-paths discipline used across the project — a 'current' report is
    just this filter evaluated at as_of = today."""
    cutoff = as_of.strftime("%Y-%m-%d")
    return [
        c for c in golden_market_data()
        if c.symbol == symbol and c.trading_date <= cutoff
    ]


def _technical_contracts_for(symbol: str, contracts: List[Any]) -> List[Any]:
    """Calls the SHIPPED MA/RSI/MACD functions — no new indicator is defined here. Declares
    input_price_basis='RAW' because the golden closes are unadjusted; claiming 'PIT_ADJUSTED'
    would be a false provenance label."""
    dates = [c.trading_date for c in contracts]
    prices = [c.close_price for c in contracts]
    if not dates:
        return []
    derived: List[Any] = []
    for compute in (compute_moving_average, compute_rsi, compute_macd):
        derived.extend(compute(
            symbol, dates, prices,
            input_price_basis="RAW", data_origin=GOLDEN_DATA_ORIGIN,
        ))
    # Only the value describing the cutoff date itself is evidence; the whole warm-up series
    # would flood the bundle with historical restatements of the same indicator.
    latest_date = dates[-1]
    return [d for d in derived if d.effective_date == latest_date]


def build_evidence_bundle(symbol: str, as_of: Any) -> Tuple[List[EvidenceItem], EvidenceBundleView]:
    """Assembles the Evidence Bundle from certified data and reports, per category, exactly what
    is present and what is not. Nothing absent is estimated or backfilled."""
    if symbol not in SYMBOL_DISPLAY_NAMES:
        raise ResearchAnalystError(
            f"FAIL CLOSED: '{symbol}' is not in the certified workbench universe."
        )
    cutoff = _as_of_datetime(as_of)

    try:
        market_contracts = _market_contracts_for(symbol, cutoff)
        items: List[EvidenceItem] = list(assemble_market_evidence(symbol, market_contracts))
        items += assemble_fundamental_evidence(
            symbol, list(golden_fundamental_data().get(symbol, [])), cutoff
        )
        items += assemble_technical_evidence(
            symbol, _technical_contracts_for(symbol, market_contracts)
        )
    except ValueError as e:
        raise ResearchAnalystError(str(e)) from e

    return items, _evidence_bundle_view(symbol, cutoff.strftime("%Y-%m-%d"), items)


def _evidence_bundle_view(symbol: str, as_of: str, items: List[EvidenceItem]) -> EvidenceBundleView:
    by_category: Dict[str, List[EvidenceItem]] = {}
    for item in items:
        by_category.setdefault(item.category, []).append(item)

    categories = []
    for category in REPORT_EVIDENCE_CATEGORIES:
        members = by_category.get(category, [])
        if category == "NEWS":
            members = by_category.get("NEWS", []) + by_category.get("ANNOUNCEMENT", [])
        categories.append(EvidenceCategoryView(
            category=category,
            available=bool(members),
            item_count=len(members),
            reason=None if members else _CATEGORY_UNAVAILABLE_REASONS.get(
                category, "Not present in the Evidence Bundle for this as_of."
            ),
            data_origins=tuple(sorted({m.data_origin for m in members})),
        ))

    breakdown: Dict[str, int] = {}
    for item in items:
        breakdown[item.data_origin] = breakdown.get(item.data_origin, 0) + 1

    return EvidenceBundleView(
        symbol=symbol, as_of=as_of,
        evidence_bundle_hash=compute_evidence_bundle_hash(items) if items else "",
        item_count=len(items),
        items=tuple(
            EvidenceItemView(
                evidence_id=i.evidence_id, category=i.category, kind=i.kind, content=i.content,
                event_date=i.event_date, source=i.source, data_origin=i.data_origin,
            ) for i in items
        ),
        categories=tuple(categories),
        data_origin_breakdown=dict(sorted(breakdown.items())),
    )


def get_evidence_bundle_view(symbol: str, as_of: Any) -> EvidenceBundleView:
    return build_evidence_bundle(symbol, as_of)[1]


# --- Report generation ----------------------------------------------------------------------------------

def _synthetic_canned_output(items: List[EvidenceItem]) -> Dict[str, Any]:
    """Fixed placeholder prose, authored here, containing no numerals — so it can never assert a
    figure, and the deterministic citation validator has nothing to fail on. Every section
    repeats that it is not analysis."""
    marker = "SYNTHETIC PLACEHOLDER — not analysis, no LLM was called."
    return {
        "summary": f"{marker} Evidence for this security was assembled and validated.",
        "technical_analysis": f"{marker} Indicator evidence appears in the bundle below.",
        "fundamental_analysis": f"{marker} Fundamental evidence appears in the bundle below.",
        "quant_analysis": f"{marker} Factor evidence, where present, appears below.",
        "news_analysis": f"{marker} News evidence, where present, appears below.",
        "bull_case": f"{marker} A constructive reading would be argued here from cited evidence.",
        "bear_case": f"{marker} A cautionary reading would be argued here from cited evidence.",
        "risk_analysis": f"{marker} Deterministic risk findings follow in the addendum below.",
        "conclusion": f"{marker} Both cases remain open; no verdict is produced by this system.",
        "evidence_ids": [i.evidence_id for i in items],
    }


def generate_analyst_report(
    symbol: str,
    as_of: Any,
    allow_synthetic_narrative: bool = False,
    persist: bool = True,
    research_run_id: Optional[str] = None,
    model: str = DEFAULT_LLM_MODEL,
    use_real_provider: Optional[bool] = None,
) -> AnalystReportView:
    """Uses the real provider when its credential is present. Fails closed when it is not,
    unless a synthetic, clearly-labelled narrative is explicitly requested. The Evidence Bundle
    is real in every case.

    `use_real_provider` forces the choice (True demands the real provider and refuses to fall
    back; False demands the synthetic path) — the default, None, decides from the preflight. A
    provider-level failure is never silently downgraded to a synthetic narrative: that would put
    unlabelled placeholder prose where a reader expects real analysis.
    """
    items, bundle_view = build_evidence_bundle(symbol, as_of)
    if not items:
        raise ResearchAnalystError(
            f"FAIL CLOSED: no evidence is available for '{symbol}' at this as_of; a report will "
            "not be generated from an empty Evidence Bundle."
        )

    real_available = _openai_credential_available()
    if use_real_provider is None:
        use_real = real_available
    else:
        use_real = use_real_provider
    if use_real and not real_available:
        raise ResearchAnalystError(
            f"FAIL CLOSED: {LLM_CREDENTIALS_UNAVAILABLE_STATUS} — the real provider was "
            f"requested but {OPENAI_API_KEY_ENV_VAR} is not set."
        )

    if not use_real and not allow_synthetic_narrative:
        raise ResearchAnalystError(
            f"FAIL CLOSED: {LLM_CREDENTIALS_UNAVAILABLE_STATUS} — no LLM credential is "
            f"configured, so no report narrative can be generated. Set "
            f"{OPENAI_API_KEY_ENV_VAR}, or explicitly request a labelled synthetic narrative."
        )

    provider: LLMProvider
    if use_real:
        provider = OpenAILLMProvider()
        narrative_origin, prompt_version, request_model = "REAL_PROVIDER", "1.0", model
    else:
        provider = FakeLLMProvider(canned_output=_synthetic_canned_output(items))
        narrative_origin = NARRATIVE_ORIGIN_SYNTHETIC
        prompt_version, request_model = "synthetic-1.0", "synthetic-placeholder"

    try:
        report = generate_research_report(
            items, provider, symbol=symbol, as_of=_as_of_datetime(as_of),
            model=request_model, prompt_version=prompt_version,
            research_run_id=research_run_id, provider_version=provider.provider_version,
            data_origin=narrative_origin,
        )
    except (ValueError, LLMProviderError) as e:
        raise ResearchAnalystError(str(e)) from e

    if persist:
        try:
            persist_research_report(get_report_store(), report)
        except ValueError as e:
            raise ResearchAnalystError(str(e)) from e

    return _report_view(report, bundle_view, evidence_integrity_verified=True)


def _report_view(
    report: ResearchReport, bundle_view: EvidenceBundleView, evidence_integrity_verified: bool,
) -> AnalystReportView:
    identity = report.identity
    dc = report.data_confidence
    return AnalystReportView(
        report_id=identity.report_id, symbol=identity.symbol, as_of=identity.as_of,
        generated_at=identity.generated_at, provider_id=identity.provider_id,
        model=identity.model, model_version=identity.model_version,
        prompt_version=identity.prompt_version,
        evidence_bundle_hash=identity.evidence_bundle_hash,
        code_version=identity.code_version, code_state=identity.code_state,
        research_run_id=identity.research_run_id,
        reproducibility_scope=identity.reproducibility_scope,
        narrative_origin=identity.data_origin,
        narrative_warning=(
            SYNTHETIC_NARRATIVE_WARNING
            if identity.data_origin == NARRATIVE_ORIGIN_SYNTHETIC else None
        ),
        sections=tuple(
            ReportSectionView(
                number=s.number, title=s.title, content_type=s.content_type, body=s.body,
                evidence_ids=s.evidence_ids, is_missing_data=s.is_missing_data,
                suppressed_ai_body=s.suppressed_ai_body,
            ) for s in report.sections
        ),
        data_confidence=DataConfidenceView(
            score=dc.score, band=dc.band, computed_by=dc.computed_by, components=dc.components,
            real_provider_ratio=dc.real_provider_ratio, origin_breakdown=dc.origin_breakdown,
            present_categories=dc.present_categories, missing_categories=dc.missing_categories,
            fact_count=dc.fact_count, model_output_count=dc.model_output_count,
            median_evidence_age_days=dc.median_evidence_age_days,
            unresolved_conflict_count=dc.unresolved_conflict_count,
            conflict_detection_scope=dc.conflict_detection_scope,
        ),
        conflicts=tuple(
            ConflictView(
                category=c.category, event_date=c.event_date, key_repr=c.key_repr,
                evidence_ids=c.evidence_ids, detection=c.detection,
            ) for c in report.conflicts
        ),
        evidence=bundle_view,
        evidence_integrity_verified=evidence_integrity_verified,
        disclaimer=report.disclaimer,
        limitations=tuple(report.limitations) + ANALYST_LIMITATIONS,
        markdown=render_report_markdown(report),
    )


# --- Persisted reports ------------------------------------------------------------------------------------

def _items_from_payload(payload: List[Dict[str, Any]]) -> List[EvidenceItem]:
    """Rebuilds EvidenceItems from the persisted canonical projection. That projection
    deliberately omits `available_at`/`received_at` (they are not part of the hashed view), so
    they come back as None — nothing rendered by this module depends on them, and the integrity
    check runs against the stored payload itself, not these reconstructions."""
    return [
        EvidenceItem(
            evidence_id=p["evidence_id"], category=p["category"], kind=p["kind"],
            content=p["content"], event_date=p.get("event_date"),
            available_at=None, received_at=None,
            source=p["source"], data_origin=p["data_origin"],
        )
        for p in payload
    ]


def get_analyst_report(report_id: str) -> AnalystReportView:
    """Re-renders a persisted report. The narrative and identity come from disk verbatim; the
    computed parts (Data Confidence, conflicts, section assembly) are re-derived deterministically
    from the persisted Evidence Bundle, so what is shown is always consistent with what is
    stored."""
    try:
        stored = get_report_store().get_report(report_id)
    except RuntimeError as e:
        raise ResearchAnalystError(str(e)) from e
    if stored is None:
        raise ResearchAnalystError(f"FAIL CLOSED: no persisted report with id '{report_id}'.")

    identity: ResearchAnalystReportIdentity = stored["identity"]
    payload = stored["evidence_payload"]
    items = _items_from_payload(payload)
    conflicts = detect_evidence_conflicts(items)
    confidence = compute_data_confidence(
        items, _as_of_datetime(identity.as_of), conflicts=conflicts
    )
    report = ResearchReport(
        identity=identity,
        sections=assemble_report_sections(stored["output"], items, confidence, conflicts),
        data_confidence=confidence, conflicts=tuple(conflicts), output=stored["output"],
        evidence_bundle=tuple(items),
    )
    return _report_view(
        report, _evidence_bundle_view(identity.symbol, identity.as_of, items),
        evidence_integrity_verified=verify_report_evidence_integrity(identity, payload),
    )


def list_analyst_reports() -> List[AnalystReportSummaryView]:
    """A report whose files are corrupt is skipped rather than crashing the listing — the same
    convention research_application.list_research_runs() already uses."""
    summaries = []
    for report_id in get_report_store().list_reports():
        try:
            view = get_analyst_report(report_id)
        except ResearchAnalystError:
            continue
        summaries.append(AnalystReportSummaryView(
            report_id=view.report_id, symbol=view.symbol, as_of=view.as_of,
            generated_at=view.generated_at, narrative_origin=view.narrative_origin,
        ))
    return summaries
