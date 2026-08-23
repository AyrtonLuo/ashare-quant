"""
fake_provider.py — Deterministic LLM Provider test doubles. No real vendor SDK is imported or
called anywhere in this file, or anywhere in src/llm/ — the directive explicitly prohibits a
real API as a test dependency.

Two distinct classes (not one class with a provider_id string param) exist specifically to
prove "provider switching": the orchestration layer (research_analyst.py) is exercised against
BOTH without any code change, demonstrating OpenAI <-> Claude <-> Gemini swappability at the
architecture level using only fakes.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.llm.provider_base import (
    LLMProvider, LLMRequest, LLMResponse, LLMTokenUsage, LLMProviderError, LLMErrorCategory,
)

# Sentinel evidence_bundle_hash values that deterministically trigger each failure mode —
# mirrors news_provider.py's PROVIDER_ERROR_SIMULATION_SYMBOL convention (a dedicated sentinel,
# not random failure injection).
TRIGGER_TIMEOUT = "__trigger_timeout__"
TRIGGER_AUTH_FAILURE = "__trigger_auth_failure__"
TRIGGER_RATE_LIMIT = "__trigger_rate_limit__"
TRIGGER_PROVIDER_UNAVAILABLE = "__trigger_provider_unavailable__"
TRIGGER_MALFORMED_RESPONSE = "__trigger_malformed_response__"
TRIGGER_EMPTY_RESPONSE = "__trigger_empty_response__"


class FakeLLMProvider(LLMProvider):
    """Deterministic fake. Returns a fixed, valid structured-output dict by default, or one of
    the failure modes above when `request.evidence_bundle_hash` is a trigger sentinel — lets
    tests exercise every failure category without any randomness or network dependency."""

    def __init__(self, provider_id: str = "fake_llm_primary", canned_output: Optional[Dict[str, Any]] = None):
        self._provider_id = provider_id
        self._canned_output = canned_output

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def provider_version(self) -> str:
        return "1.0.0-fake"

    def generate_structured_research(self, request: LLMRequest) -> LLMResponse:
        trigger = request.evidence_bundle_hash

        if trigger == TRIGGER_TIMEOUT:
            raise LLMProviderError(self.provider_id, LLMErrorCategory.TIMEOUT, "simulated request timeout.")
        if trigger == TRIGGER_AUTH_FAILURE:
            raise LLMProviderError(self.provider_id, LLMErrorCategory.AUTHENTICATION_FAILURE, "simulated authentication failure.")
        if trigger == TRIGGER_RATE_LIMIT:
            raise LLMProviderError(self.provider_id, LLMErrorCategory.RATE_LIMIT, "simulated rate limit exceeded.")
        if trigger == TRIGGER_PROVIDER_UNAVAILABLE:
            raise LLMProviderError(self.provider_id, LLMErrorCategory.PROVIDER_UNAVAILABLE, "simulated provider outage.")

        start = time.monotonic()
        if trigger == TRIGGER_MALFORMED_RESPONSE:
            raw_output: Any = "not a dict — malformed"
        elif trigger == TRIGGER_EMPTY_RESPONSE:
            raw_output = {}
        else:
            raw_output = self._canned_output or _default_canned_output()
        latency = time.monotonic() - start

        return LLMResponse(
            request_id=request.request_id, provider_id=self.provider_id, model=request.model,
            model_version="fake-v1", raw_structured_output=raw_output,
            token_usage=LLMTokenUsage(prompt_tokens=100, completion_tokens=200, total_tokens=300),
            latency_seconds=latency, received_at=datetime.now(timezone.utc).replace(tzinfo=None),
            data_origin="SYNTHETIC_DATA",
        )


class AlternateFakeLLMProvider(LLMProvider):
    """A second, independently-implemented fake — used specifically to prove the Research
    Analyst orchestration function works unchanged when the provider is swapped. Same
    `canned_output` constructor knob as FakeLLMProvider, for the same reason."""

    def __init__(self, canned_output: Optional[Dict[str, Any]] = None):
        self._canned_output = canned_output

    @property
    def provider_id(self) -> str:
        return "fake_llm_alternate"

    @property
    def provider_version(self) -> str:
        return "2.0.0-fake"

    def generate_structured_research(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            request_id=request.request_id, provider_id=self.provider_id, model=request.model,
            model_version=None, raw_structured_output=self._canned_output or _default_canned_output(),
            token_usage=LLMTokenUsage(prompt_tokens=50, completion_tokens=150, total_tokens=200),
            latency_seconds=0.01, received_at=datetime.now(timezone.utc).replace(tzinfo=None),
            data_origin="SYNTHETIC_DATA",
        )


def _default_canned_output() -> Dict[str, Any]:
    """A schema-valid placeholder (non-empty evidence_ids) usable wherever a test only cares
    that parsing succeeds — NOT usable as-is for a test that also runs citation validation
    against a real evidence bundle, since "EV-DEFAULT" won't exist in one. Tests needing full
    citation-validation success must pass an explicit `canned_output` citing real evidence_ids."""
    return {
        "summary": "Deterministic test summary.", "technical_analysis": "Test technical analysis.",
        "fundamental_analysis": "Test fundamental analysis.", "quant_analysis": "Test quant analysis.",
        "news_analysis": "Test news analysis.", "bull_case": "Test bull case.",
        "bear_case": "Test bear case.", "risk_analysis": "Test risk analysis.",
        "conclusion": "Test conclusion.", "evidence_ids": ["EV-DEFAULT"],
    }
