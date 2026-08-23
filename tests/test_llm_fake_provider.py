"""
test_llm_fake_provider.py — FakeLLMProvider / AlternateFakeLLMProvider: provider interface
conformance and every directive-required failure category, all deterministic, no network.
"""

import pytest

from src.llm.provider_base import LLMRequest, LLMProviderError, LLMErrorCategory
from src.llm.fake_provider import (
    FakeLLMProvider, AlternateFakeLLMProvider,
    TRIGGER_TIMEOUT, TRIGGER_AUTH_FAILURE, TRIGGER_RATE_LIMIT, TRIGGER_PROVIDER_UNAVAILABLE,
    TRIGGER_MALFORMED_RESPONSE, TRIGGER_EMPTY_RESPONSE,
)


def _request(hash_value="normal_hash"):
    return LLMRequest(
        request_id="r1", model="m1", prompt_version="1.0",
        evidence_bundle_hash=hash_value, evidence_payload=[{"a": 1}],
    )


def test_provider_interface_conformance():
    provider = FakeLLMProvider()
    assert provider.provider_id == "fake_llm_primary"
    assert provider.provider_version
    response = provider.generate_structured_research(_request())
    assert response.request_id == "r1"
    assert response.provider_id == "fake_llm_primary"


def test_valid_response():
    provider = FakeLLMProvider()
    response = provider.generate_structured_research(_request())
    assert isinstance(response.raw_structured_output, dict)
    assert response.token_usage.total_tokens > 0


def test_timeout_raises_explicit_category():
    provider = FakeLLMProvider()
    with pytest.raises(LLMProviderError) as exc_info:
        provider.generate_structured_research(_request(TRIGGER_TIMEOUT))
    assert exc_info.value.category == LLMErrorCategory.TIMEOUT


def test_authentication_failure_raises_explicit_category():
    provider = FakeLLMProvider()
    with pytest.raises(LLMProviderError) as exc_info:
        provider.generate_structured_research(_request(TRIGGER_AUTH_FAILURE))
    assert exc_info.value.category == LLMErrorCategory.AUTHENTICATION_FAILURE


def test_rate_limit_raises_explicit_category():
    provider = FakeLLMProvider()
    with pytest.raises(LLMProviderError) as exc_info:
        provider.generate_structured_research(_request(TRIGGER_RATE_LIMIT))
    assert exc_info.value.category == LLMErrorCategory.RATE_LIMIT


def test_provider_unavailable_raises_explicit_category():
    provider = FakeLLMProvider()
    with pytest.raises(LLMProviderError) as exc_info:
        provider.generate_structured_research(_request(TRIGGER_PROVIDER_UNAVAILABLE))
    assert exc_info.value.category == LLMErrorCategory.PROVIDER_UNAVAILABLE


def test_malformed_response_returned_not_raised_by_provider_but_caught_downstream():
    """The fake simulates a provider that RETURNS a malformed payload (as a real vendor's SDK
    might) rather than raising — proving parse_structured_output(), not the provider itself,
    is what catches this. See test_research_analyst_llm_orchestration.py for the full chain."""
    provider = FakeLLMProvider()
    response = provider.generate_structured_research(_request(TRIGGER_MALFORMED_RESPONSE))
    assert not isinstance(response.raw_structured_output, dict)


def test_empty_response_returned_not_raised_by_provider():
    provider = FakeLLMProvider()
    response = provider.generate_structured_research(_request(TRIGGER_EMPTY_RESPONSE))
    assert response.raw_structured_output == {}


# --- Provider switching ------------------------------------------------------------------------

def test_provider_switching_alternate_conforms_to_same_interface():
    alt = AlternateFakeLLMProvider()
    assert alt.provider_id == "fake_llm_alternate"
    response = alt.generate_structured_research(_request())
    assert response.provider_id == "fake_llm_alternate"
    assert isinstance(response.raw_structured_output, dict)


def test_provider_switching_both_providers_produce_valid_parseable_output():
    from src.llm.structured_output import parse_structured_output
    for provider in (FakeLLMProvider(), AlternateFakeLLMProvider()):
        response = provider.generate_structured_research(_request())
        output = parse_structured_output(response.raw_structured_output)
        assert output.summary
