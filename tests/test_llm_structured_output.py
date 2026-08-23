"""
test_llm_structured_output.py — StructuredResearchOutput schema validation.
"""

import pytest

from src.llm.structured_output import parse_structured_output, StructuredResearchOutput


def _valid_raw(**overrides):
    base = dict(
        summary="s", technical_analysis="t", fundamental_analysis="f", quant_analysis="q",
        news_analysis="n", bull_case="b", bear_case="be", risk_analysis="r", conclusion="c",
        evidence_ids=["EV-1"],
    )
    base.update(overrides)
    return base


def test_valid_response_parses():
    output = parse_structured_output(_valid_raw())
    assert isinstance(output, StructuredResearchOutput)
    assert output.evidence_ids == ["EV-1"]


def test_missing_field_fails_closed():
    raw = _valid_raw()
    del raw["bull_case"]
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        parse_structured_output(raw)


def test_wrong_datatype_fails_closed():
    raw = _valid_raw(summary=12345)
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        parse_structured_output(raw)


def test_evidence_ids_wrong_datatype_fails_closed():
    raw = _valid_raw(evidence_ids="EV-1")
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        parse_structured_output(raw)


def test_malformed_response_not_a_dict_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        parse_structured_output("a giant unstructured block of text")


def test_empty_response_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        parse_structured_output({})


def test_empty_narrative_field_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        StructuredResearchOutput(
            summary="", technical_analysis="t", fundamental_analysis="f", quant_analysis="q",
            news_analysis="n", bull_case="b", bear_case="be", risk_analysis="r", conclusion="c",
            evidence_ids=["EV-1"],
        )


def test_empty_evidence_ids_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        StructuredResearchOutput(
            summary="s", technical_analysis="t", fundamental_analysis="f", quant_analysis="q",
            news_analysis="n", bull_case="b", bear_case="be", risk_analysis="r", conclusion="c",
            evidence_ids=[],
        )
