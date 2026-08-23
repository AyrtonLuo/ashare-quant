"""
test_research_report_generation.py — Research Report Generation Layer (proposal §7).

Covers the ten-section report, evidence traceability, missing-data marking, conflict surfacing,
Bull/Bear/Risk, the computed Data Confidence metric, malformed LLM output, every fail-closed
path, and integration with the Step 5 Identity/Store.
"""

import dataclasses
from datetime import datetime

import pytest

from src.data.contracts.derived import DerivedDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.contracts.market_data import MarketDataContract
from src.llm.fake_provider import AlternateFakeLLMProvider, FakeLLMProvider
from src.llm.provider_base import (
    LLMErrorCategory,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    LLMTokenUsage,
)
from src.quant.evidence.evidence_item import (
    EvidenceItem,
    assemble_fundamental_evidence,
    assemble_market_evidence,
    compute_evidence_bundle_hash,
)
from src.quant.research_report.data_confidence import (
    CONFLICT_DETECTION_SCOPE,
    REPORT_EVIDENCE_CATEGORIES,
    compute_data_confidence,
    detect_evidence_conflicts,
)
from src.quant.research_report.report import (
    NOT_INVESTMENT_ADVICE_DISCLAIMER,
    ReportSection,
    ResearchReport,
    assemble_report_sections,
    derive_section_evidence_ids,
    generate_research_report,
    persist_research_report,
    render_report_markdown,
)
from src.quant.research_report.report_identity import (
    REPRODUCIBILITY_SCOPE_EVIDENCE_ONLY,
    verify_report_evidence_integrity,
)
from src.quant.research_report.report_store import ResearchAnalystReportStore

SYMBOL = "600519.SH"
AS_OF = datetime(2026, 8, 1)


# --- evidence helpers -------------------------------------------------------------------------

def _market_item(close=100.5, trading_date="2026-08-01", origin="GOLDEN_DATASET"):
    return MarketDataContract(
        symbol=SYMBOL, timestamp=datetime(2026, 8, 1), trading_date=trading_date,
        open_price=100.0, high_price=101.0, low_price=99.0, close_price=close,
        volume=1000.0, amount=100500.0, adj_factor=1.0, unadjusted_close=close,
        trading_status="NORMAL", quality_status="VALID", data_origin=origin,
    )


def _market_evidence(close=100.5, origin="GOLDEN_DATASET"):
    return assemble_market_evidence(SYMBOL, [_market_item(close=close, origin=origin)])


def _fundamental_evidence(pe=25.0):
    c = FundamentalDataContract(
        symbol=SYMBOL, trade_date="2026-08-01", report_date="2026-06-30",
        announcement_date="2026-07-15", currency="CNY", revenue=1000.0, net_income=100.0,
        eps_annual=1.0, eps_ttm=1.0, book_value_per_share=10.0, operating_cash_flow=200.0,
        shares_outstanding=1000000.0, market_cap=100000000.0, pe_lyr=20.0, pe_ttm=pe,
        pe_ttm_status="VALID", pb=2.0, pb_status="VALID", dividend_yield_ttm=0.02,
        dividend_yield_status="VALID", roe=0.15, quality_status="VALID",
        available_at=datetime(2026, 7, 15), received_at=datetime(2026, 7, 15, 0, 5),
        data_origin="GOLDEN_DATASET",
    )
    return assemble_fundamental_evidence(SYMBOL, [c], AS_OF)


def _synthetic_item(category, kind, content, evidence_id, event_date="2026-07-31",
                    origin="GOLDEN_DATASET"):
    """A hand-built EvidenceItem for categories with no implemented assembly function
    (QUANT_FACTOR / RISK). Built through the real EvidenceItem constructor, so its own
    __post_init__ validation still applies."""
    return EvidenceItem(
        evidence_id=evidence_id, category=category, kind=kind, content=content,
        event_date=event_date, available_at=None, received_at=None,
        source="test_fixture", data_origin=origin,
    )


def _full_bundle():
    return (
        _market_evidence()
        + _fundamental_evidence()
        + [
            _synthetic_item("TECHNICAL", "MODEL_OUTPUT",
                            {"indicator": "MA", "value": 98.25, "parameters": {"window": 20},
                             "lookback_window": 20},
                            "TECHNICAL-aaaa00000001"),
            _synthetic_item("QUANT_FACTOR", "MODEL_OUTPUT",
                            {"factor": "value_composite", "z_score": 1.75},
                            "QUANT_FACTOR-bbbb00000001"),
            _synthetic_item("NEWS", "FACT",
                            {"title": "Interim results released", "relevance_score": 0.9},
                            "NEWS-cccc00000001"),
            _synthetic_item("RISK", "MODEL_OUTPUT",
                            {"max_drawdown": 0.12, "volatility": 0.31},
                            "RISK-dddd00000001"),
        ]
    )


def _canned(evidence_ids, **overrides):
    out = {
        "summary": "Close was 100.5.", "technical_analysis": "MA sits at 98.25.",
        "fundamental_analysis": "PE ttm is 25.0.", "quant_analysis": "Z score is 1.75.",
        "news_analysis": "Interim results released.", "bull_case": "Momentum is constructive.",
        "bear_case": "Valuation is stretched.", "risk_analysis": "Max drawdown 0.12.",
        "conclusion": "Both cases remain open.", "evidence_ids": evidence_ids,
    }
    out.update(overrides)
    return out


def _provider_for(bundle, **overrides):
    return FakeLLMProvider(
        canned_output=_canned([e.evidence_id for e in bundle], **overrides)
    )


class _RawOutputProvider(LLMProvider):
    """Returns a caller-chosen raw structured output. Built on the real LLMProvider ABC so the
    report layer is exercised through exactly the interface a real provider implements."""

    def __init__(self, raw):
        self._raw = raw

    @property
    def provider_id(self):
        return "stub_raw_output"

    @property
    def provider_version(self):
        return "1.0.0-stub"

    def generate_structured_research(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            request_id=request.request_id, provider_id=self.provider_id, model=request.model,
            model_version="stub-v1", raw_structured_output=self._raw,
            token_usage=LLMTokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            latency_seconds=0.0, received_at=datetime(2026, 8, 1, 12, 0, 0),
            data_origin="SYNTHETIC_DATA",
        )


class _FailingProvider(LLMProvider):
    """Raises a provider-level failure, to prove the report layer never swallows one."""

    def __init__(self, category=LLMErrorCategory.TIMEOUT):
        self._category = category

    @property
    def provider_id(self):
        return "stub_failing"

    @property
    def provider_version(self):
        return "1.0.0-stub"

    def generate_structured_research(self, request: LLMRequest) -> LLMResponse:
        raise LLMProviderError(self.provider_id, self._category, "simulated provider failure.")


def _numberless_canned(evidence_ids):
    """Narrative with no numerals at all — every number in prose must trace to cited evidence,
    so a bundle missing a category cannot be described with that category's figures."""
    return {
        "summary": "A qualitative summary.", "technical_analysis": "Trend commentary.",
        "fundamental_analysis": "Valuation commentary.", "quant_analysis": "Factor commentary.",
        "news_analysis": "Disclosure commentary.", "bull_case": "Constructive reading.",
        "bear_case": "Cautious reading.", "risk_analysis": "Risk commentary.",
        "conclusion": "Both cases remain open.", "evidence_ids": evidence_ids,
    }


def _numberless_provider(bundle):
    return FakeLLMProvider(canned_output=_numberless_canned([e.evidence_id for e in bundle]))


def _generate(bundle=None, provider=None, **kwargs):
    bundle = _full_bundle() if bundle is None else bundle
    provider = provider or _provider_for(bundle)
    return generate_research_report(
        bundle, provider, symbol=SYMBOL, as_of=AS_OF, model="fake-model-1", **kwargs
    )


# --- 10-section completeness ---------------------------------------------------------------------

def test_report_has_exactly_the_ten_proposal_sections():
    report = _generate()
    assert [s.number for s in report.sections] == list(range(1, 11))
    assert [s.title for s in report.sections] == [
        "Executive Summary", "Technical Analysis", "Fundamental Analysis",
        "Quant Factor Analysis", "News / Event Analysis", "Bull Case", "Bear Case",
        "Risk Analysis", "Data Confidence", "Final Research Conclusion",
    ]


def test_every_section_has_a_non_empty_body_and_content_type():
    report = _generate()
    for section in report.sections:
        assert section.body.strip()
        assert section.content_type


def test_sections_carry_the_fact_model_output_ai_distinction():
    report = _generate().section_by_number
    assert sections_type(report, 1) == "AI_INTERPRETATION"
    assert "AI_INTERPRETATION" in sections_type(report, 2)
    assert "MODEL_OUTPUT" in sections_type(report, 2)
    assert sections_type(report, 9) == "MODEL_OUTPUT"  # Data Confidence is never AI-authored
    assert "AI_INTERPRETATION" not in sections_type(report, 9)


def sections_type(by_number, n):
    return by_number[n].content_type


def test_report_is_frozen_and_has_no_verdict_field():
    """No single buy/sell conclusion — enforced by there being nowhere to put one."""
    field_names = {f.name for f in dataclasses.fields(ResearchReport)}
    for forbidden in ("verdict", "rating", "recommendation", "signal", "action", "target_price"):
        assert forbidden not in field_names
    report = _generate()
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.disclaimer = "x"


def test_report_carries_mandatory_disclaimer_and_limitations():
    report = _generate()
    assert report.disclaimer == NOT_INVESTMENT_ADVICE_DISCLAIMER
    assert "not investment advice" in report.disclaimer.lower()
    joined = " ".join(report.limitations)
    assert "NOT bit-reproducible" in joined
    assert "semantic fact-checking" in joined


# --- Bull / Bear / Risk ----------------------------------------------------------------------------

def test_bull_and_bear_are_both_present_and_distinct():
    report = _generate().section_by_number
    assert report[6].body.strip() and report[7].body.strip()
    assert report[6].body.strip() != report[7].body.strip()


def test_identical_bull_and_bear_fails_closed():
    bundle = _full_bundle()
    provider = _provider_for(bundle, bull_case="Same text.", bear_case="Same text.")
    with pytest.raises(ValueError, match="Bull Case and Bear Case are identical"):
        _generate(bundle, provider)


def test_risk_addendum_appears_only_in_the_risk_section():
    report = _generate()
    with_addendum = [s.number for s in report.sections
                     if "DETERMINISTIC RISK ADDENDUM" in s.body]
    assert with_addendum == [8]


def test_risk_section_carries_a_deterministic_code_generated_addendum():
    report = _generate().section_by_number
    body = report[8].body
    assert "DETERMINISTIC RISK ADDENDUM (code-generated, not AI-authored)" in body
    assert "UNRESOLVED EVIDENCE CONFLICTS" in body
    assert "MISSING EVIDENCE CATEGORIES" in body


# --- Evidence citation / traceability ---------------------------------------------------------------

def test_sections_with_numbers_attribute_the_evidence_that_backs_them():
    report = _generate().section_by_number
    assert "TECHNICAL-aaaa00000001" in report[2].evidence_ids   # "MA sits at 98.25"
    assert "QUANT_FACTOR-bbbb00000001" in report[4].evidence_ids  # "Z score is 1.75"
    assert report[3].evidence_ids  # "PE ttm is 25.0"


def test_section_without_numbers_attributes_no_evidence_rather_than_guessing():
    bundle = _full_bundle()
    cited = [e for e in bundle]
    assert derive_section_evidence_ids("No figures appear in this sentence.", cited) == ()


def test_derived_attribution_never_invents_an_unknown_evidence_id():
    report = _generate()
    bundle_ids = {e.evidence_id for e in report.evidence_bundle}
    for section in report.sections:
        for eid in section.evidence_ids:
            assert eid in bundle_ids


def test_untraceable_number_fails_the_whole_report_closed():
    """Inherited unmodified from the citation validator — the report layer never relaxes it."""
    bundle = _full_bundle()
    provider = _provider_for(bundle, summary="Close was 4242.42.")
    with pytest.raises(ValueError, match="citation validation failed"):
        _generate(bundle, provider)


def test_invented_evidence_id_fails_the_whole_report_closed():
    bundle = _full_bundle()
    provider = FakeLLMProvider(canned_output=_canned(["MARKET-doesnotexist"]))
    with pytest.raises(ValueError, match="citation validation failed"):
        _generate(bundle, provider)


def test_ai_interpretation_never_becomes_evidence():
    """The bundle after generation is byte-identical to the bundle before it: no report prose
    was fed back in as an EvidenceItem."""
    bundle = _full_bundle()
    before = compute_evidence_bundle_hash(bundle)
    report = _generate(bundle)
    assert compute_evidence_bundle_hash(list(report.evidence_bundle)) == before
    assert all(item.kind in ("FACT", "MODEL_OUTPUT") for item in report.evidence_bundle)


# --- Missing data ------------------------------------------------------------------------------------

def _bundle_without(category):
    return [e for e in _full_bundle() if e.category != category]


@pytest.mark.parametrize("category,section_number", [
    ("TECHNICAL", 2), ("FUNDAMENTAL", 3), ("QUANT_FACTOR", 4), ("NEWS", 5),
])
def test_absent_category_is_marked_not_available_never_estimated(category, section_number):
    bundle = _bundle_without(category)
    section = _generate(bundle, _numberless_provider(bundle)).section_by_number[section_number]
    assert section.is_missing_data is True
    assert section.body.startswith("NOT AVAILABLE")
    assert "approximated" in section.body
    assert "backfilled" in section.body


def test_suppressed_ai_text_is_retained_not_silently_discarded():
    bundle = _bundle_without("QUANT_FACTOR")
    report = _generate(bundle, _numberless_provider(bundle)).section_by_number
    assert report[4].suppressed_ai_body == "Factor commentary."
    assert report[4].evidence_ids == ()


def test_present_sections_are_not_marked_missing():
    report = _generate()
    assert not any(s.is_missing_data for s in report.sections)
    assert all(s.suppressed_ai_body is None for s in report.sections)


def test_missing_categories_are_surfaced_in_risk_addendum_and_confidence():
    bundle = _bundle_without("RISK")
    report = _generate(bundle, _numberless_provider(bundle))
    assert "RISK" in report.data_confidence.missing_categories
    assert "MISSING EVIDENCE CATEGORIES (reported, never estimated): RISK" in \
        report.section_by_number[8].body


# --- Conflicts ------------------------------------------------------------------------------------------

def test_conflicting_market_values_for_the_same_date_are_detected():
    bundle = _market_evidence(close=100.5) + _market_evidence(close=103.5)
    conflicts = detect_evidence_conflicts(bundle)
    assert len(conflicts) == 1
    assert conflicts[0].category == "MARKET"
    assert conflicts[0].detection == "DETERMINISTIC_VALUE_DISAGREEMENT"
    assert len(conflicts[0].evidence_ids) == 2


def test_conflict_detection_never_resolves_a_conflict():
    """Both sides survive into the bundle and into the flag — nothing is dropped or chosen."""
    bundle = _market_evidence(close=100.5) + _market_evidence(close=103.5)
    conflict = detect_evidence_conflicts(bundle)[0]
    assert set(conflict.evidence_ids) == {e.evidence_id for e in bundle}


def test_non_conflicting_evidence_produces_no_conflicts():
    assert detect_evidence_conflicts(_full_bundle()) == []


def test_distinct_news_items_are_not_treated_as_conflicts():
    """Semantic contradiction between free-text news is not deterministically decidable, so it
    is not claimed — the disclosed scope, asserted."""
    bundle = [
        _synthetic_item("NEWS", "FACT", {"title": "Deal is on"}, "NEWS-1111"),
        _synthetic_item("NEWS", "FACT", {"title": "Deal is off"}, "NEWS-2222"),
    ]
    assert detect_evidence_conflicts(bundle) == []
    assert "NOT deterministically detectable" in CONFLICT_DETECTION_SCOPE


def test_conflicts_are_surfaced_explicitly_in_the_report():
    bundle = _market_evidence(close=100.5) + _market_evidence(close=103.5) + _fundamental_evidence()
    provider = _provider_for(
        bundle, summary="Two sources report 100.5 and 103.5.",
        technical_analysis="No indicator evidence.", quant_analysis="No factor evidence.",
        news_analysis="No news.", risk_analysis="Sources disagree.",
        fundamental_analysis="PE ttm is 25.0.",
    )
    report = _generate(bundle, provider)
    assert report.data_confidence.unresolved_conflict_count == 1
    body = report.section_by_number[8].body
    assert "UNRESOLVED EVIDENCE CONFLICTS: 1" in body
    assert "none resolved" in body


def test_conflicts_are_deterministically_ordered():
    bundle = _market_evidence(close=100.5) + _market_evidence(close=103.5)
    assert detect_evidence_conflicts(bundle) == detect_evidence_conflicts(bundle)


# --- Data Confidence ----------------------------------------------------------------------------------------

def test_data_confidence_is_computed_by_code_never_self_rated():
    report = _generate()
    assert report.data_confidence.computed_by == "DETERMINISTIC_CODE"
    assert report.section_by_number[9].content_type == "MODEL_OUTPUT"
    assert "never self-rated by the model" in report.section_by_number[9].body


def test_data_confidence_is_deterministic():
    bundle = _full_bundle()
    a = compute_data_confidence(bundle, AS_OF)
    b = compute_data_confidence(bundle, AS_OF)
    assert a == b


def test_data_confidence_score_is_reproducible_from_its_components():
    from src.quant.research_report.data_confidence import _WEIGHTS
    dc = compute_data_confidence(_full_bundle(), AS_OF)
    active = sum(_WEIGHTS[name] for name in dc.components)
    recomputed = round(
        sum(dc.components[name] * _WEIGHTS[name] for name in dc.components) / active, 6
    )
    assert recomputed == dc.score
    assert 0.0 <= dc.score <= 1.0
    assert dc.band in ("HIGH", "MEDIUM", "LOW")


def test_real_provider_evidence_scores_higher_than_synthetic():
    golden = _market_evidence(origin="GOLDEN_DATASET")
    real = _market_evidence(origin="REAL_PROVIDER")
    assert compute_data_confidence(real, AS_OF).components["origin"] == 1.0
    assert compute_data_confidence(golden, AS_OF).components["origin"] == 0.0
    assert compute_data_confidence(real, AS_OF).score > compute_data_confidence(golden, AS_OF).score


def test_missing_categories_lower_coverage_and_score():
    full = compute_data_confidence(_full_bundle(), AS_OF)
    partial = compute_data_confidence(_bundle_without("QUANT_FACTOR"), AS_OF)
    assert full.components["coverage"] > partial.components["coverage"]
    assert full.missing_categories == ()
    assert partial.missing_categories == ("QUANT_FACTOR",)
    assert set(full.present_categories) == set(REPORT_EVIDENCE_CATEGORIES)


def test_conflicts_lower_the_confidence_score():
    clean = _market_evidence(close=100.5)
    conflicted = _market_evidence(close=100.5) + _market_evidence(close=103.5)
    assert compute_data_confidence(conflicted, AS_OF).components["conflict"] < \
        compute_data_confidence(clean, AS_OF).components["conflict"]


def test_stale_evidence_scores_lower_recency_than_fresh():
    fresh = compute_data_confidence(_full_bundle(), AS_OF)
    stale = compute_data_confidence(_full_bundle(), datetime(2027, 8, 1))
    assert stale.components["recency"] < fresh.components["recency"]
    assert stale.median_evidence_age_days > fresh.median_evidence_age_days


def test_recency_is_omitted_not_faked_when_no_evidence_carries_a_date():
    undated = [_synthetic_item("MARKET", "FACT", {"close": 1.0}, "MARKET-nodate", event_date=None)]
    dc = compute_data_confidence(undated, AS_OF)
    assert dc.dated_evidence_count == 0
    assert dc.median_evidence_age_days is None
    assert "recency" not in dc.components  # excluded from the weighting, never scored as 0 or 1


def test_data_confidence_counts_facts_and_model_outputs_separately():
    dc = compute_data_confidence(_full_bundle(), AS_OF)
    assert dc.fact_count + dc.model_output_count == dc.evidence_count
    assert dc.fact_count > 0 and dc.model_output_count > 0


def test_data_confidence_on_empty_bundle_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_data_confidence([], AS_OF)


# --- Malformed LLM output / provider failures --------------------------------------------------------------

@pytest.mark.parametrize("bad_output,expected", [
    ({}, "empty structured output"),
    ({"summary": "s"}, "missing required field"),
    ("not a dict", "malformed structured output"),
    (["a", "list"], "malformed structured output"),
])
def test_malformed_llm_output_fails_the_report_closed(bad_output, expected):
    with pytest.raises(ValueError, match=expected):
        _generate(_full_bundle(), _RawOutputProvider(bad_output))


def test_wrong_datatype_in_llm_output_fails_closed():
    bundle = _full_bundle()
    raw = _canned([e.evidence_id for e in bundle], bull_case=12345)
    with pytest.raises(ValueError, match="wrong datatype"):
        _generate(bundle, _RawOutputProvider(raw))


def test_empty_evidence_ids_in_llm_output_fails_closed():
    raw = _canned([])
    with pytest.raises(ValueError, match="must not be empty"):
        _generate(_full_bundle(), _RawOutputProvider(raw))


@pytest.mark.parametrize("category", [
    LLMErrorCategory.TIMEOUT, LLMErrorCategory.AUTHENTICATION_FAILURE,
    LLMErrorCategory.RATE_LIMIT, LLMErrorCategory.PROVIDER_UNAVAILABLE,
])
def test_provider_failure_propagates_unswallowed(category):
    with pytest.raises(LLMProviderError) as excinfo:
        _generate(_full_bundle(), _FailingProvider(category))
    assert excinfo.value.category == category


def test_no_report_is_produced_when_generation_fails():
    """Fail closed means nothing partial escapes — not a report with an empty section."""
    with pytest.raises(LLMProviderError):
        _generate(_full_bundle(), _FailingProvider())


def test_empty_evidence_bundle_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        generate_research_report(
            [], FakeLLMProvider(), symbol=SYMBOL, as_of=AS_OF, model="fake-model-1"
        )


# --- Identity / Store integration ---------------------------------------------------------------------------

def test_report_identity_is_built_and_anchored_to_the_bundle():
    bundle = _full_bundle()
    report = _generate(bundle)
    assert report.identity.evidence_bundle_hash == compute_evidence_bundle_hash(bundle)
    assert report.identity.symbol == SYMBOL
    assert report.identity.as_of == "2026-08-01"
    assert report.identity.reproducibility_scope == REPRODUCIBILITY_SCOPE_EVIDENCE_ONLY


def test_report_persists_through_the_step_5_store_and_verifies(tmp_path):
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    report = _generate(research_run_id="run_1", data_snapshot_id="snap_1")
    report_id = persist_research_report(store, report)

    loaded = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports")).get_report(report_id)
    assert loaded["identity"] == report.identity
    assert loaded["output"] == report.output
    assert loaded["identity"].research_run_id == "run_1"
    assert verify_report_evidence_integrity(loaded["identity"], loaded["evidence_payload"])


def test_persisting_the_same_report_twice_fails_closed(tmp_path):
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    report = _generate()
    persist_research_report(store, report)
    with pytest.raises(ValueError, match="IMMUTABLE"):
        persist_research_report(store, report)


def test_two_reports_over_one_bundle_share_the_hash_but_not_the_prose(tmp_path):
    """The honest reproducibility boundary, end to end at report level."""
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    bundle = _full_bundle()

    a = _generate(bundle, _provider_for(bundle, conclusion="Both cases remain open."))
    b = _generate(bundle, _provider_for(bundle, conclusion="Neither case is settled."))
    persist_research_report(store, a)
    persist_research_report(store, b)

    assert a.identity.evidence_bundle_hash == b.identity.evidence_bundle_hash
    assert a.section_by_number[10].body != b.section_by_number[10].body
    assert a.identity.report_id != b.identity.report_id


def test_provider_switching_produces_a_report_from_either_provider():
    bundle = _full_bundle()
    alt = AlternateFakeLLMProvider(canned_output=_canned([e.evidence_id for e in bundle]))
    report = _generate(bundle, alt)
    assert report.identity.provider_id == alt.provider_id
    assert len(report.sections) == 10


# --- Rendering ------------------------------------------------------------------------------------------------

def test_markdown_rendering_contains_every_section_and_the_disclaimer():
    report = _generate()
    md = render_report_markdown(report)
    for section in report.sections:
        assert f"## {section.number}. {section.title}" in md
    assert NOT_INVESTMENT_ADVICE_DISCLAIMER in md
    assert report.identity.evidence_bundle_hash in md
    assert "reproducibility_scope" in md
    assert "## Limitations" in md


def test_markdown_rendering_flags_missing_data_visibly():
    bundle = _bundle_without("TECHNICAL")
    report = _generate(bundle, _numberless_provider(bundle))
    md = render_report_markdown(report)
    assert "**MISSING DATA**" in md
    assert "NOT AVAILABLE" in md
    assert "retained, not discarded" in md


def test_assemble_report_sections_is_pure_and_repeatable():
    bundle = _full_bundle()
    report = _generate(bundle)
    conflicts = detect_evidence_conflicts(bundle)
    confidence = compute_data_confidence(bundle, AS_OF, conflicts=conflicts)
    again = assemble_report_sections(report.output, bundle, confidence, conflicts)
    assert again == report.sections
    assert all(isinstance(s, ReportSection) for s in again)
