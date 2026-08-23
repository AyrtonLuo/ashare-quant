"""
test_llm_provider_base.py — LLMRequest/LLMResponse/LLMTokenUsage/LLMProviderError.
"""

from datetime import datetime

import pytest

from src.llm.provider_base import (
    LLMRequest, LLMResponse, LLMTokenUsage, LLMProviderError, LLMErrorCategory, LLMProvider,
)


def test_llm_request_valid_construction():
    req = LLMRequest(
        request_id="r1", model="m1", prompt_version="1.0",
        evidence_bundle_hash="h1", evidence_payload=[{"a": 1}],
    )
    assert req.timeout_seconds == 60.0


def test_llm_request_empty_id_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        LLMRequest(request_id="", model="m1", prompt_version="1.0", evidence_bundle_hash="h1", evidence_payload=[])


def test_llm_request_empty_model_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        LLMRequest(request_id="r1", model="", prompt_version="1.0", evidence_bundle_hash="h1", evidence_payload=[])


def test_llm_request_invalid_timeout_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        LLMRequest(request_id="r1", model="m1", prompt_version="1.0", evidence_bundle_hash="h1",
                   evidence_payload=[], timeout_seconds=0)


def test_llm_response_valid_construction():
    resp = LLMResponse(
        request_id="r1", provider_id="p1", model="m1", model_version="v1",
        raw_structured_output={}, token_usage=LLMTokenUsage(1, 1, 2),
        latency_seconds=0.5, received_at=datetime(2026, 8, 1),
    )
    assert resp.data_origin == "SYNTHETIC_DATA"


def test_llm_response_negative_latency_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        LLMResponse(
            request_id="r1", provider_id="p1", model="m1", model_version=None,
            raw_structured_output={}, token_usage=LLMTokenUsage(1, 1, 2),
            latency_seconds=-1.0, received_at=datetime(2026, 8, 1),
        )


def test_token_usage_negative_fails_closed():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        LLMTokenUsage(prompt_tokens=-1, completion_tokens=1, total_tokens=0)


def test_llm_provider_error_has_explicit_category():
    err = LLMProviderError("p1", LLMErrorCategory.TIMEOUT, "timed out")
    assert err.category == LLMErrorCategory.TIMEOUT
    assert err.provider_id == "p1"
    assert "TIMEOUT" in str(err)


def test_all_error_categories_are_distinct_and_directive_complete():
    """The directive's item 6 checklist: timeout, authentication failure, rate limit, malformed
    response, empty response, provider unavailable, invalid structured output, missing
    credential — every one must have an explicit status."""
    names = {c.value for c in LLMErrorCategory}
    assert names == {
        "TIMEOUT", "AUTHENTICATION_FAILURE", "RATE_LIMIT", "MALFORMED_RESPONSE",
        "EMPTY_RESPONSE", "PROVIDER_UNAVAILABLE", "INVALID_STRUCTURED_OUTPUT",
        "CREDENTIALS_UNAVAILABLE",
    }


def test_llm_provider_is_abstract_cannot_instantiate():
    with pytest.raises(TypeError):
        LLMProvider()
