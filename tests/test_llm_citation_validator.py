"""
test_llm_citation_validator.py — Deterministic citation / numeric-hallucination validation.
"""

from src.quant.evidence.evidence_item import EvidenceItem
from src.llm.structured_output import StructuredResearchOutput
from src.llm.citation_validator import validate_citations


def _evidence(evidence_id="EV-1", content=None):
    return EvidenceItem(
        evidence_id=evidence_id, category="MARKET", kind="FACT",
        content=content or {"close": 100.5}, event_date="2026-08-01",
        available_at=None, received_at=None, source="test", data_origin="SYNTHETIC_DATA",
    )


def _output(**overrides):
    base = dict(
        summary="Price closed at 100.5.", technical_analysis="t", fundamental_analysis="f",
        quant_analysis="q", news_analysis="n", bull_case="b", bear_case="be",
        risk_analysis="r", conclusion="c", evidence_ids=["EV-1"],
    )
    base.update(overrides)
    return StructuredResearchOutput(**base)


def test_valid_citations_pass():
    is_valid, errors = validate_citations(_output(), [_evidence()])
    assert is_valid is True
    assert errors == []


def test_invalid_evidence_id_fails():
    is_valid, errors = validate_citations(_output(evidence_ids=["EV-DOES-NOT-EXIST"]), [_evidence()])
    assert is_valid is False
    assert any("not present in the evidence bundle" in e for e in errors)


def test_unsupported_evidence_not_in_this_requests_bundle_fails():
    """The id exists SOMEWHERE (e.g. from a different request), but was not part of the bundle
    actually sent for THIS request — must fail exactly like an unknown id."""
    other_request_bundle = [_evidence(evidence_id="EV-FROM-ANOTHER-REQUEST")]
    is_valid, errors = validate_citations(_output(evidence_ids=["EV-FROM-ANOTHER-REQUEST"]), other_request_bundle)
    assert is_valid is True  # sanity: it IS in ITS OWN bundle

    this_requests_bundle = [_evidence(evidence_id="EV-1")]
    is_valid2, errors2 = validate_citations(
        _output(evidence_ids=["EV-FROM-ANOTHER-REQUEST"]), this_requests_bundle,
    )
    assert is_valid2 is False
    assert any("not present in the evidence bundle" in e for e in errors2)


def test_unsupported_number_in_narrative_fails():
    output = _output(summary="Price closed at 999.99, a huge jump.")
    is_valid, errors = validate_citations(output, [_evidence(content={"close": 100.5})])
    assert is_valid is False
    assert any("not traceable to any cited evidence" in e for e in errors)


def test_number_traceable_to_nested_evidence_content_passes():
    output = _output(
        summary="RSI reading of 65.5 suggests momentum.",
        technical_analysis="t", fundamental_analysis="f", quant_analysis="q", news_analysis="n",
        bull_case="b", bear_case="be", risk_analysis="r", conclusion="c",
    )
    evidence = _evidence(content={"indicator": "RSI_14", "value": 65.5, "parameters": {"window": 14}})
    is_valid, errors = validate_citations(output, [evidence])
    assert is_valid is True, errors


def test_number_only_in_uncited_evidence_fails():
    """A number present in the bundle but NOT in a cited item must not count as support —
    citing evidence and using its numbers are two separate, both-required checks."""
    cited = _evidence(evidence_id="EV-1", content={"close": 100.5})
    uncited = _evidence(evidence_id="EV-2", content={"close": 999.99})
    output = _output(summary="Price closed at 999.99.", evidence_ids=["EV-1"])
    is_valid, errors = validate_citations(output, [cited, uncited])
    assert is_valid is False
