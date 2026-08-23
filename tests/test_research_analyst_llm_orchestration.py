"""
test_research_analyst_llm_orchestration.py — Evidence Bundle -> LLM Provider -> Structured
Output -> Deterministic Validator, the full chain, and the Evidence Boundary / no-bypass-path
guarantees the directive's second-pass audit requires.
"""

from datetime import datetime

import pytest

from src.data.contracts.market_data import MarketDataContract
from src.quant.evidence.evidence_item import assemble_market_evidence, compute_evidence_bundle_hash
from src.llm.provider_base import LLMProviderError, LLMErrorCategory
from src.llm.fake_provider import FakeLLMProvider, AlternateFakeLLMProvider, TRIGGER_TIMEOUT
from src.llm.research_analyst import generate_ai_research_output, AIResearchOutputResult

SYMBOL = "600519.SH"


def _market_evidence(close_price=100.5):
    m = MarketDataContract(
        symbol=SYMBOL, timestamp=datetime(2026, 8, 1), trading_date="2026-08-01",
        open_price=100.0, high_price=101.0, low_price=99.0, close_price=close_price,
        volume=1000.0, amount=100500.0, adj_factor=1.0, unadjusted_close=close_price,
        trading_status="NORMAL", quality_status="VALID", data_origin="GOLDEN_DATASET",
    )
    return assemble_market_evidence(SYMBOL, [m])


def _canned_output(evidence_ids, summary="Price closed at 100.5."):
    return {
        "summary": summary, "technical_analysis": "t", "fundamental_analysis": "f",
        "quant_analysis": "q", "news_analysis": "n", "bull_case": "b", "bear_case": "be",
        "risk_analysis": "r", "conclusion": "c", "evidence_ids": evidence_ids,
    }


# --- Full chain: valid response ------------------------------------------------------------

def test_full_chain_valid_response_produces_validated_output():
    evidence = _market_evidence()
    provider = FakeLLMProvider(canned_output=_canned_output([evidence[0].evidence_id]))
    result = generate_ai_research_output(evidence, provider, model="fake-model-1")

    assert isinstance(result, AIResearchOutputResult)
    assert result.output.evidence_ids == [evidence[0].evidence_id]
    assert result.identity.provider_id == "fake_llm_primary"
    assert result.identity.model == "fake-model-1"
    assert result.identity.evidence_bundle_hash == compute_evidence_bundle_hash(evidence)


# --- Deterministic Evidence Bundle hash --------------------------------------------------------

def test_evidence_bundle_hash_deterministic_across_calls():
    evidence = _market_evidence()
    h1 = compute_evidence_bundle_hash(evidence)
    h2 = compute_evidence_bundle_hash(evidence)
    assert h1 == h2

    provider = FakeLLMProvider(canned_output=_canned_output([evidence[0].evidence_id]))
    result1 = generate_ai_research_output(evidence, provider, model="m1", request_id="req-fixed-1")
    result2 = generate_ai_research_output(evidence, provider, model="m1", request_id="req-fixed-2")
    assert result1.identity.evidence_bundle_hash == result2.identity.evidence_bundle_hash


def test_evidence_bundle_hash_changes_with_content():
    e1 = _market_evidence(close_price=100.5)
    e2 = _market_evidence(close_price=200.0)
    assert compute_evidence_bundle_hash(e1) != compute_evidence_bundle_hash(e2)


# --- Provider switching, through the orchestration layer ---------------------------------------

def test_provider_switching_orchestration_unchanged_for_both_providers():
    evidence = _market_evidence()
    for provider in (
        FakeLLMProvider(canned_output=_canned_output([evidence[0].evidence_id])),
        AlternateFakeLLMProvider(canned_output=_canned_output([evidence[0].evidence_id])),
    ):
        result = generate_ai_research_output(evidence, provider, model="m1")
        assert isinstance(result, AIResearchOutputResult)
        assert result.identity.provider_id == provider.provider_id


# --- Fail-closed paths -----------------------------------------------------------------------

def test_empty_evidence_bundle_fails_closed():
    provider = FakeLLMProvider()
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        generate_ai_research_output([], provider, model="m1")


def test_provider_error_propagates_not_swallowed(monkeypatch):
    """FakeLLMProvider's failure triggers key off evidence_bundle_hash — force it
    deterministically by monkeypatching compute_evidence_bundle_hash for this one test, rather
    than depending on a real hash collision."""
    import src.llm.research_analyst as research_analyst_module
    monkeypatch.setattr(research_analyst_module, "compute_evidence_bundle_hash", lambda _bundle: TRIGGER_TIMEOUT)

    evidence = _market_evidence()
    provider = FakeLLMProvider()
    with pytest.raises(LLMProviderError) as exc_info:
        generate_ai_research_output(evidence, provider, model="m1")
    assert exc_info.value.category == LLMErrorCategory.TIMEOUT


def test_citation_validation_failure_propagates_fail_closed():
    evidence = _market_evidence()
    provider = FakeLLMProvider(canned_output=_canned_output(["EV-DOES-NOT-EXIST"]))
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        generate_ai_research_output(evidence, provider, model="m1")


def test_malformed_provider_response_propagates_fail_closed(monkeypatch):
    from src.llm.fake_provider import TRIGGER_MALFORMED_RESPONSE
    import src.llm.research_analyst as research_analyst_module
    monkeypatch.setattr(research_analyst_module, "compute_evidence_bundle_hash", lambda _bundle: TRIGGER_MALFORMED_RESPONSE)

    evidence = _market_evidence()
    provider = FakeLLMProvider()
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        generate_ai_research_output(evidence, provider, model="m1")


# --- Evidence Boundary / no-bypass-path (second-pass audit support) ----------------------------

def test_ai_interpretation_output_is_not_an_evidence_item_and_has_no_conversion_path():
    """Directive item 5: AI Interpretation must never become Evidence. Structural proof: the
    StructuredResearchOutput type has no method producing an EvidenceItem, and EvidenceItem's
    own kind validation rejects "AI_INTERPRETATION" outright (see test_evidence_layer.py)."""
    from src.llm.structured_output import StructuredResearchOutput
    assert not hasattr(StructuredResearchOutput, "to_evidence_item")
    assert not hasattr(StructuredResearchOutput, "as_evidence")


def test_llm_request_carries_no_database_or_api_client_handle():
    """Structural Evidence Boundary proof: LLMRequest's only content field is evidence_payload
    (a plain list of dicts) -- there is no field through which a live DB/News-API/Market-API
    handle or search capability could reach a provider implementation."""
    from src.llm.provider_base import LLMRequest
    field_names = set(LLMRequest.__dataclass_fields__.keys())
    assert field_names == {
        "request_id", "model", "prompt_version", "evidence_bundle_hash", "evidence_payload",
        "timeout_seconds", "max_tokens", "temperature",
    }
