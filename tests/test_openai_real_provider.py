"""
test_openai_real_provider.py — the real OpenAI LLM provider (src/llm/openai_provider.py).

Offline tests run against a local HTTP stub bound to 127.0.0.1, so every status-code mapping,
malformed-response path and security property is exercised deterministically with no network
access and no cost. The single real, billable API call lives in the last test, gated on the
credential preflight exactly like the existing live-provider tests
(`@pytest.mark.real_provider` + skip when credentials are absent).

Every Fake Provider test in the suite is retained unchanged; this file adds to them.
"""

import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.llm.credential import LLMProviderCredentialPreflight
from src.llm.fake_provider import AlternateFakeLLMProvider, FakeLLMProvider
from src.llm.openai_provider import (
    OPENAI_API_KEY_ENV_VAR,
    OPENAI_PROVIDER_ID,
    SYSTEM_PROMPT,
    OpenAILLMProvider,
    _structured_output_json_schema,
)
from src.llm.provider_base import (
    LLMErrorCategory,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
)
from src.llm.research_analyst import generate_ai_research_output
from src.llm.structured_output import REQUIRED_STRUCTURED_OUTPUT_FIELDS

FAKE_KEY = "sk-test-key-not-a-real-credential-0123456789"
EVIDENCE_PAYLOAD = [
    {"evidence_id": "MARKET-abc123", "category": "MARKET", "kind": "FACT",
     "content": {"close": 100.5}, "event_date": "2026-08-01", "source": "t",
     "data_origin": "GOLDEN_DATASET"},
]


# --- local stub server ---------------------------------------------------------------------

class _StubState:
    status = 200
    body = ""
    last_request = None


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        _StubState.last_request = {"headers": dict(self.headers), "body": json.loads(raw)}
        payload = _StubState.body.encode("utf-8")
        self.send_response(_StubState.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass  # keep the test output clean; this stub is not under test


@pytest.fixture()
def stub_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _StubState.status, _StubState.body, _StubState.last_request = 200, "", None
    yield f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
    server.shutdown()
    server.server_close()


@pytest.fixture(autouse=True)
def _fake_key(request, monkeypatch):
    """Offline tests run against the stub with a fake key. The real-API test must NOT be given
    the fake one — it needs the genuine environment credential, or it must skip."""
    if request.node.get_closest_marker("real_llm_provider"):
        return
    monkeypatch.setenv(OPENAI_API_KEY_ENV_VAR, FAKE_KEY)


def _ok_body(overrides=None, content=None):
    output = {name: "text" for name in REQUIRED_STRUCTURED_OUTPUT_FIELDS
              if name != "evidence_ids"}
    output["evidence_ids"] = ["MARKET-abc123"]
    body = {
        "model": "gpt-4o-2024-08-06",
        "choices": [{"message": {"content": content if content is not None
                                 else json.dumps(output)}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }
    if overrides:
        body.update(overrides)
    return json.dumps(body)


def _request(**overrides):
    base = dict(
        request_id="req_1", model="gpt-4o", prompt_version="1.0",
        evidence_bundle_hash="a" * 64, evidence_payload=EVIDENCE_PAYLOAD,
        timeout_seconds=10.0,
    )
    base.update(overrides)
    return LLMRequest(**base)


def _provider(url):
    return OpenAILLMProvider(api_base_url=url)


# --- interface conformance -------------------------------------------------------------------

def test_implements_the_shipped_provider_interface():
    provider = OpenAILLMProvider()
    assert isinstance(provider, LLMProvider)
    assert provider.provider_id == OPENAI_PROVIDER_ID
    assert provider.provider_version


def test_constructing_a_provider_performs_no_io_and_reads_no_credential(monkeypatch):
    monkeypatch.delenv(OPENAI_API_KEY_ENV_VAR, raising=False)
    OpenAILLMProvider()  # must not raise — the key is looked up per request, not at construction


def test_no_vendor_sdk_is_imported():
    import src.llm.openai_provider as module
    source = open(module.__file__).read()
    for sdk in ("import openai", "from openai", "import anthropic", "import requests",
                "import httpx"):
        assert sdk not in source


# --- happy path -------------------------------------------------------------------------------

def test_valid_response_produces_a_real_provider_llm_response(stub_server):
    _StubState.body = _ok_body()
    response = _provider(stub_server).generate_structured_research(_request())

    assert response.request_id == "req_1"
    assert response.provider_id == OPENAI_PROVIDER_ID
    assert response.model == "gpt-4o"
    assert response.model_version == "gpt-4o-2024-08-06"   # provider-resolved, not echoed
    assert response.data_origin == "REAL_PROVIDER"
    assert response.token_usage.total_tokens == 30
    assert response.latency_seconds >= 0
    assert isinstance(response.received_at, datetime)
    assert set(response.raw_structured_output) == set(REQUIRED_STRUCTURED_OUTPUT_FIELDS)


# --- security: the key, the evidence boundary, the schema ----------------------------------------

def test_api_key_is_sent_as_a_header_and_never_appears_in_the_body(stub_server):
    _StubState.body = _ok_body()
    _provider(stub_server).generate_structured_research(_request())
    sent = _StubState.last_request
    assert sent["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert FAKE_KEY not in json.dumps(sent["body"])


@pytest.mark.parametrize("status", [401, 403, 429, 500, 400])
def test_api_key_never_leaks_into_an_error_message(stub_server, status):
    _StubState.status, _StubState.body = status, json.dumps({"error": "denied"})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert FAKE_KEY not in str(excinfo.value)
    assert FAKE_KEY not in excinfo.value.error_message


def test_missing_credential_fails_closed_before_any_network_access(monkeypatch):
    monkeypatch.delenv(OPENAI_API_KEY_ENV_VAR, raising=False)
    # An unroutable port: if a socket were opened at all this would surface as a connection
    # error instead of the credential error asserted below.
    provider = OpenAILLMProvider(api_base_url="http://127.0.0.1:1/v1/chat/completions")
    with pytest.raises(LLMProviderError) as excinfo:
        provider.generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.CREDENTIALS_UNAVAILABLE


def test_request_body_carries_evidence_and_grants_the_model_no_tools(stub_server):
    _StubState.body = _ok_body()
    _provider(stub_server).generate_structured_research(_request())
    body = _StubState.last_request["body"]

    assert "tools" not in body and "functions" not in body and "tool_choice" not in body
    assert body["messages"][0]["content"] == SYSTEM_PROMPT
    user_content = body["messages"][1]["content"]
    assert "MARKET-abc123" in user_content
    assert json.dumps(EVIDENCE_PAYLOAD[0]["content"], sort_keys=True) in user_content.replace(
        " ", ""
    ) or "100.5" in user_content


def test_request_pins_a_strict_json_schema_built_from_the_shipped_constants(stub_server):
    _StubState.body = _ok_body()
    _provider(stub_server).generate_structured_research(_request())
    schema = _StubState.last_request["body"]["response_format"]

    assert schema["type"] == "json_schema"
    assert schema["json_schema"]["strict"] is True
    assert schema["json_schema"]["schema"]["additionalProperties"] is False
    assert set(schema["json_schema"]["schema"]["required"]) == set(
        REQUIRED_STRUCTURED_OUTPUT_FIELDS
    )


def test_schema_cannot_drift_from_the_structured_output_contract():
    schema = _structured_output_json_schema()["schema"]
    assert set(schema["properties"]) == set(REQUIRED_STRUCTURED_OUTPUT_FIELDS)
    assert schema["properties"]["evidence_ids"]["type"] == "array"


def test_empty_evidence_bundle_is_refused_before_the_call(stub_server):
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request(evidence_payload=[]))
    assert excinfo.value.category == LLMErrorCategory.INVALID_STRUCTURED_OUTPUT
    assert _StubState.last_request is None


# --- error mapping ------------------------------------------------------------------------------

@pytest.mark.parametrize("status,expected", [
    (401, LLMErrorCategory.AUTHENTICATION_FAILURE),
    (403, LLMErrorCategory.AUTHENTICATION_FAILURE),
    (429, LLMErrorCategory.RATE_LIMIT),
    (408, LLMErrorCategory.TIMEOUT),
    (504, LLMErrorCategory.TIMEOUT),
    (500, LLMErrorCategory.PROVIDER_UNAVAILABLE),
    (503, LLMErrorCategory.PROVIDER_UNAVAILABLE),
    (400, LLMErrorCategory.PROVIDER_UNAVAILABLE),
])
def test_http_status_maps_to_exactly_one_error_category(stub_server, status, expected):
    _StubState.status, _StubState.body = status, json.dumps({"error": {"message": "x"}})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == expected
    assert excinfo.value.provider_id == OPENAI_PROVIDER_ID


def test_unreachable_endpoint_is_provider_unavailable():
    provider = OpenAILLMProvider(api_base_url="http://127.0.0.1:1/v1/chat/completions")
    with pytest.raises(LLMProviderError) as excinfo:
        provider.generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.PROVIDER_UNAVAILABLE


def test_timeout_maps_to_the_timeout_category(stub_server, monkeypatch):
    import socket as socket_module
    import urllib.request

    def _raise_timeout(*args, **kwargs):
        raise socket_module.timeout("simulated socket timeout")

    monkeypatch.setattr(urllib.request, "urlopen", _raise_timeout)
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request(timeout_seconds=0.5))
    assert excinfo.value.category == LLMErrorCategory.TIMEOUT
    assert "0.5" in excinfo.value.error_message


@pytest.mark.parametrize("body,expected", [
    ("not json at all", LLMErrorCategory.MALFORMED_RESPONSE),
    ("[1, 2, 3]", LLMErrorCategory.MALFORMED_RESPONSE),
])
def test_non_json_or_non_object_body_is_malformed(stub_server, body, expected):
    _StubState.body = body
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == expected


def test_no_choices_is_an_empty_response(stub_server):
    _StubState.body = json.dumps({"choices": [], "usage": {}})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.EMPTY_RESPONSE


def test_blank_content_is_an_empty_response(stub_server):
    _StubState.body = _ok_body(content="   ")
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.EMPTY_RESPONSE


def test_provider_refusal_is_invalid_structured_output(stub_server):
    _StubState.body = json.dumps({
        "model": "gpt-4o", "choices": [{"message": {"refusal": "I cannot help with that"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.INVALID_STRUCTURED_OUTPUT


def test_truncated_response_is_malformed_not_silently_parsed(stub_server):
    _StubState.body = _ok_body(
        overrides={"choices": [{"message": {"content": '{"summary": "cut off'},
                                "finish_reason": "length"}]}
    )
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.MALFORMED_RESPONSE
    assert "truncated" in excinfo.value.error_message


def test_content_that_is_not_json_is_malformed(stub_server):
    _StubState.body = _ok_body(content="I am prose, not JSON.")
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.MALFORMED_RESPONSE


def test_missing_usage_block_is_malformed_never_backfilled_with_zeros(stub_server):
    _StubState.body = _ok_body(overrides={"usage": None})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.MALFORMED_RESPONSE
    assert "token provenance" in excinfo.value.error_message


def test_incomplete_usage_block_is_malformed(stub_server):
    _StubState.body = _ok_body(overrides={"usage": {"prompt_tokens": 1}})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.MALFORMED_RESPONSE


# --- a fake can never impersonate a real provider ---------------------------------------------------

def test_fake_providers_never_claim_real_provider_origin():
    from src.llm.fake_provider import _default_canned_output  # noqa: F401  (existence check)
    for provider in (FakeLLMProvider(), AlternateFakeLLMProvider()):
        response = provider.generate_structured_research(_request())
        assert response.data_origin == "SYNTHETIC_DATA"
        assert response.provider_id != OPENAI_PROVIDER_ID


def test_only_the_real_provider_emits_real_provider_origin(stub_server):
    _StubState.body = _ok_body()
    real = _provider(stub_server).generate_structured_research(_request())
    fake = FakeLLMProvider().generate_structured_research(_request())
    assert (real.data_origin, fake.data_origin) == ("REAL_PROVIDER", "SYNTHETIC_DATA")


# --- the chain, against the stub: Evidence -> Provider -> Structured Output -> Validator ------------

def test_full_chain_through_the_real_provider_class(stub_server):
    from src.quant.evidence.evidence_item import EvidenceItem

    evidence = [EvidenceItem(
        evidence_id="MARKET-abc123", category="MARKET", kind="FACT",
        content={"close": 100.5}, event_date="2026-08-01", available_at=None,
        received_at=None, source="t", data_origin="GOLDEN_DATASET",
    )]
    output = {name: "Qualitative commentary." for name in REQUIRED_STRUCTURED_OUTPUT_FIELDS
              if name != "evidence_ids"}
    output["evidence_ids"] = ["MARKET-abc123"]
    _StubState.body = _ok_body(content=json.dumps(output))

    result = generate_ai_research_output(
        evidence, _provider(stub_server), model="gpt-4o", prompt_version="1.0",
    )
    assert result.identity.provider_id == OPENAI_PROVIDER_ID
    assert result.identity.model_version == "gpt-4o-2024-08-06"
    assert result.output.evidence_ids == ["MARKET-abc123"]


def test_validator_still_fails_a_real_provider_response_closed(stub_server):
    """The provider being real earns it no exemption from citation validation."""
    from src.quant.evidence.evidence_item import EvidenceItem

    evidence = [EvidenceItem(
        evidence_id="MARKET-abc123", category="MARKET", kind="FACT",
        content={"close": 100.5}, event_date="2026-08-01", available_at=None,
        received_at=None, source="t", data_origin="GOLDEN_DATASET",
    )]
    output = {name: "Qualitative commentary." for name in REQUIRED_STRUCTURED_OUTPUT_FIELDS
              if name != "evidence_ids"}
    output["summary"] = "The close was 4242.42."      # untraceable number
    output["evidence_ids"] = ["MARKET-abc123"]
    _StubState.body = _ok_body(content=json.dumps(output))

    with pytest.raises(ValueError, match="citation validation failed"):
        generate_ai_research_output(evidence, _provider(stub_server), model="gpt-4o")


def test_full_report_chain_through_the_real_provider_class(stub_server):
    """Evidence -> OpenAILLMProvider -> Structured Output -> Validator -> 10-section Research
    Report, driven through the real provider class against a local stub. This verifies every
    link of the mandated chain except the vendor round-trip itself, which the test below
    exercises when the account has quota."""
    from src.quant.evidence.evidence_item import EvidenceItem
    from src.quant.research_report.report import generate_research_report

    evidence = [EvidenceItem(
        evidence_id="MARKET-abc123", category="MARKET", kind="FACT",
        content={"close": 100.5}, event_date="2026-08-01", available_at=None,
        received_at=None, source="t", data_origin="GOLDEN_DATASET",
    )]
    output = {name: "Qualitative commentary." for name in REQUIRED_STRUCTURED_OUTPUT_FIELDS
              if name != "evidence_ids"}
    output["bull_case"] = "A constructive reading."
    output["bear_case"] = "A cautious reading."
    output["evidence_ids"] = ["MARKET-abc123"]
    _StubState.body = _ok_body(content=json.dumps(output))

    report = generate_research_report(
        evidence, _provider(stub_server), symbol="600519.SH", as_of=datetime(2026, 8, 1),
        model="gpt-4o", prompt_version="1.0", data_origin="REAL_PROVIDER",
    )
    assert len(report.sections) == 10
    assert report.identity.provider_id == OPENAI_PROVIDER_ID
    assert report.identity.data_origin == "REAL_PROVIDER"
    assert report.identity.model_version == "gpt-4o-2024-08-06"
    assert report.data_confidence.computed_by == "DETERMINISTIC_CODE"


# --- the one real, billable API call ------------------------------------------------------------------

@pytest.mark.real_llm_provider
def test_real_end_to_end_evidence_to_validated_report():
    """Evidence -> real OpenAI API -> Structured Output -> Validator -> Research Report.

    Gated exactly like the existing live-provider tests: skipped, never failed, when the
    credential is absent. Kept deliberately small (one evidence item, one call) — it spends real
    tokens every time the suite runs with a key present."""
    preflight = LLMProviderCredentialPreflight.inspect_credentials(
        OPENAI_PROVIDER_ID, OPENAI_API_KEY_ENV_VAR
    )
    if preflight["credential_status"] != "PRESENT_UNVERIFIED":
        pytest.skip(
            "LLM_PROVIDER_CREDENTIALS_UNAVAILABLE: OPENAI_API_KEY not available in environment."
        )

    from src.quant.evidence.evidence_item import EvidenceItem
    from src.quant.research_report.report import generate_research_report

    evidence = [
        EvidenceItem(
            evidence_id="MARKET-e2e000000001", category="MARKET", kind="FACT",
            content={"trading_date": "2026-08-01", "close": 100.5, "volume": 1000},
            event_date="2026-08-01", available_at=None, received_at=None,
            source="MarketDataContract", data_origin="GOLDEN_DATASET",
        ),
        EvidenceItem(
            evidence_id="FUNDAMENTAL-e2e000000001", category="FUNDAMENTAL", kind="FACT",
            content={"report_date": "2026-06-30", "pe_ttm": 25.0},
            event_date="2026-06-30", available_at=None, received_at=None,
            source="FundamentalDataContract", data_origin="GOLDEN_DATASET",
        ),
    ]

    try:
        report = generate_research_report(
            evidence, OpenAILLMProvider(), symbol="600519.SH", as_of=datetime(2026, 8, 1),
            model="gpt-4o-mini", prompt_version="1.0", data_origin="REAL_PROVIDER",
        )
    except LLMProviderError as e:
        # An exhausted account quota is an environment/billing condition, not a code defect, and
        # is reported as such rather than dressed up as a pass. Deliberately NARROW: only an
        # insufficient-quota 429 skips. Authentication failures, timeouts, malformed responses
        # and ordinary rate limits all still FAIL loudly, because any of those could be a real
        # regression in this provider.
        if e.category is LLMErrorCategory.RATE_LIMIT and "quota" in e.error_message.lower():
            pytest.skip(
                "LLM_PROVIDER_QUOTA_UNAVAILABLE: the OPENAI_API_KEY authenticated successfully "
                "but the account has no remaining quota, so the real end-to-end call could not "
                "complete. This is NOT a verification — add billing credit and re-run."
            )
        raise

    assert len(report.sections) == 10
    assert report.identity.provider_id == OPENAI_PROVIDER_ID
    assert report.identity.data_origin == "REAL_PROVIDER"
    assert report.identity.model_version                      # provider-resolved snapshot id
    assert report.output.bull_case.strip() != report.output.bear_case.strip()
    assert set(report.output.evidence_ids) <= {e.evidence_id for e in evidence}
    assert report.data_confidence.computed_by == "DETERMINISTIC_CODE"
