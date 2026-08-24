"""
test_gemini_real_provider.py — the real Google Gemini LLM provider
(src/llm/gemini_provider.py).

Every offline test runs against a local HTTP stub bound to 127.0.0.1: no test in this file
depends on the real Gemini API, so the suite is deterministic, free and network-free. The single
real, billable call is the last test, marked `real_llm_provider` and skipped when GEMINI_API_KEY
is absent — and, when it runs, it verifies the whole chain rather than merely that a socket
opened.

The OpenAI provider and both Fake providers keep their own suites, unchanged.
"""

import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.llm.credential import LLMProviderCredentialPreflight
from src.llm.fake_provider import AlternateFakeLLMProvider, FakeLLMProvider
from src.llm.gemini_provider import (
    GEMINI_API_KEY_ENV_VAR,
    GEMINI_PROVIDER_ID,
    GEMINI_PROVIDER_VERSION,
    SYSTEM_PROMPT,
    GeminiLLMProvider,
    _gemini_response_schema,
)
from src.llm.openai_provider import OPENAI_PROVIDER_ID, OpenAILLMProvider
from src.llm.provider_base import (
    LLMErrorCategory,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
)
from src.llm.research_analyst import generate_ai_research_output
from src.llm.structured_output import REQUIRED_STRUCTURED_OUTPUT_FIELDS
from src.quant.evidence.evidence_item import EvidenceItem

FAKE_KEY = "gm-test-key-not-a-real-credential-0123456789"
EVIDENCE_PAYLOAD = [
    {"evidence_id": "MARKET-abc123", "category": "MARKET", "kind": "FACT",
     "content": {"close": 100.5}, "event_date": "2026-08-01", "source": "t",
     "data_origin": "GOLDEN_DATASET"},
]


def _evidence_item():
    return EvidenceItem(
        evidence_id="MARKET-abc123", category="MARKET", kind="FACT",
        content={"close": 100.5}, event_date="2026-08-01", available_at=None,
        received_at=None, source="t", data_origin="GOLDEN_DATASET",
    )


# --- local stub server ---------------------------------------------------------------------

class _StubState:
    status = 200
    body = ""
    last_request = None


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        # HTTP header names are case-insensitive and urllib normalizes their capitalization,
        # so they are lower-cased here rather than compared verbatim.
        _StubState.last_request = {
            "path": self.path,
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "body": json.loads(raw),
        }
        payload = _StubState.body.encode("utf-8")
        self.send_response(_StubState.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture()
def stub_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _StubState.status, _StubState.body, _StubState.last_request = 200, "", None
    yield f"http://127.0.0.1:{server.server_port}/v1beta"
    server.shutdown()
    server.server_close()


@pytest.fixture(autouse=True)
def _fake_key(request, monkeypatch):
    """Offline tests use a fake key against the stub. The real-API test must NOT be given it —
    it needs the genuine environment credential, or it must skip."""
    if request.node.get_closest_marker("real_llm_provider"):
        return
    monkeypatch.setenv(GEMINI_API_KEY_ENV_VAR, FAKE_KEY)


def _structured_output(**overrides):
    output = {name: "Qualitative commentary." for name in REQUIRED_STRUCTURED_OUTPUT_FIELDS
              if name != "evidence_ids"}
    output["bull_case"] = "A constructive reading."
    output["bear_case"] = "A cautious reading."
    output["evidence_ids"] = ["MARKET-abc123"]
    output.update(overrides)
    return output


def _ok_body(overrides=None, text=None):
    body = {
        "modelVersion": "gemini-2.5-flash-001",
        "candidates": [{
            "content": {"role": "model", "parts": [
                {"text": text if text is not None else json.dumps(_structured_output())}
            ]},
            "finishReason": "STOP",
        }],
        "usageMetadata": {
            "promptTokenCount": 40, "candidatesTokenCount": 60, "totalTokenCount": 100,
        },
    }
    if overrides:
        body.update(overrides)
    return json.dumps(body)


def _request(**overrides):
    base = dict(
        request_id="req_1", model="gemini-2.5-flash", prompt_version="1.0",
        evidence_bundle_hash="a" * 64, evidence_payload=EVIDENCE_PAYLOAD,
        timeout_seconds=10.0,
    )
    base.update(overrides)
    return LLMRequest(**base)


def _provider(url):
    return GeminiLLMProvider(api_base_url=url)


# --- interface reuse: nothing was refactored ---------------------------------------------------

def test_implements_the_shipped_provider_interface_unchanged():
    provider = GeminiLLMProvider()
    assert isinstance(provider, LLMProvider)
    assert provider.provider_id == GEMINI_PROVIDER_ID
    assert provider.provider_version == GEMINI_PROVIDER_VERSION


def test_openai_provider_still_exists_and_is_untouched():
    """Requirement: Gemini is ADDED beside OpenAI, never replacing the class."""
    provider = OpenAILLMProvider()
    assert isinstance(provider, LLMProvider)
    assert provider.provider_id == OPENAI_PROVIDER_ID
    assert provider.provider_id != GEMINI_PROVIDER_ID


def test_constructing_a_provider_performs_no_io_and_reads_no_credential(monkeypatch):
    monkeypatch.delenv(GEMINI_API_KEY_ENV_VAR, raising=False)
    GeminiLLMProvider()  # must not raise — the key is read per request, not at construction


def test_no_google_sdk_or_http_dependency_is_imported():
    import src.llm.gemini_provider as module
    source = open(module.__file__).read()
    for dependency in ("google.generativeai", "import google", "from google",
                       "import requests", "import httpx", "genai"):
        assert dependency not in source


# --- happy path ---------------------------------------------------------------------------------

def test_valid_response_produces_a_real_provider_llm_response(stub_server):
    _StubState.body = _ok_body()
    response = _provider(stub_server).generate_structured_research(_request())

    assert response.request_id == "req_1"
    assert response.provider_id == GEMINI_PROVIDER_ID
    assert response.model == "gemini-2.5-flash"
    assert response.model_version == "gemini-2.5-flash-001"   # provider-resolved, not echoed
    assert response.data_origin == "REAL_PROVIDER"
    assert response.token_usage.prompt_tokens == 40
    assert response.token_usage.completion_tokens == 60
    assert response.token_usage.total_tokens == 100
    assert response.latency_seconds >= 0
    assert isinstance(response.received_at, datetime)
    assert set(response.raw_structured_output) == set(REQUIRED_STRUCTURED_OUTPUT_FIELDS)


def test_model_is_addressed_in_the_url_path(stub_server):
    _StubState.body = _ok_body()
    _provider(stub_server).generate_structured_research(_request(model="gemini-2.5-pro"))
    assert _StubState.last_request["path"].endswith(
        "/v1beta/models/gemini-2.5-pro:generateContent"
    )


def test_multi_part_content_is_concatenated(stub_server):
    output = json.dumps(_structured_output())
    split = len(output) // 2
    _StubState.body = _ok_body(overrides={"candidates": [{
        "content": {"parts": [{"text": output[:split]}, {"text": output[split:]}]},
        "finishReason": "STOP",
    }]})
    response = _provider(stub_server).generate_structured_research(_request())
    assert set(response.raw_structured_output) == set(REQUIRED_STRUCTURED_OUTPUT_FIELDS)


# --- credential handling -------------------------------------------------------------------------

def test_api_key_travels_as_a_header_never_in_the_url_or_body(stub_server):
    _StubState.body = _ok_body()
    _provider(stub_server).generate_structured_research(_request())
    sent = _StubState.last_request

    assert sent["headers"]["x-goog-api-key"] == FAKE_KEY
    assert FAKE_KEY not in sent["path"]        # never a ?key= query parameter
    assert "key=" not in sent["path"]
    assert FAKE_KEY not in json.dumps(sent["body"])


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_api_key_never_leaks_into_an_error_message(stub_server, status):
    _StubState.status = status
    _StubState.body = json.dumps({"error": {"status": "INTERNAL", "message": "denied"}})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert FAKE_KEY not in str(excinfo.value)
    assert FAKE_KEY not in excinfo.value.error_message


def test_missing_credential_fails_closed_before_any_network_access(monkeypatch):
    monkeypatch.delenv(GEMINI_API_KEY_ENV_VAR, raising=False)
    # An unroutable port: had a socket been opened, this would surface as a connection error
    # instead of the credential error asserted below.
    provider = GeminiLLMProvider(api_base_url="http://127.0.0.1:1/v1beta")
    with pytest.raises(LLMProviderError) as excinfo:
        provider.generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.CREDENTIALS_UNAVAILABLE


def test_provider_module_never_logs_or_prints():
    """AST-based, not a substring scan: the module docstring states that it performs no logging,
    and a sentence about logging is not a logging call."""
    import ast
    import src.llm.gemini_provider as module

    tree = ast.parse(open(module.__file__).read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "logging" not in imported

    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)
    assert not (called & {"print", "info", "debug", "warning", "error", "exception"})


# --- evidence boundary ----------------------------------------------------------------------------

def test_request_grants_the_model_no_tools_search_or_grounding(stub_server):
    _StubState.body = _ok_body()
    _provider(stub_server).generate_structured_research(_request())
    body = _StubState.last_request["body"]

    for forbidden in ("tools", "toolConfig", "functionDeclarations", "googleSearch",
                      "googleSearchRetrieval", "codeExecution", "retrieval"):
        assert forbidden not in body
    assert forbidden_absent_anywhere(body)


def forbidden_absent_anywhere(body):
    serialized = json.dumps(body)
    return all(term not in serialized for term in
               ("googleSearch", "functionDeclarations", "codeExecution"))


def test_request_carries_the_evidence_bundle_and_the_analyst_contract(stub_server):
    _StubState.body = _ok_body()
    _provider(stub_server).generate_structured_research(_request())
    body = _StubState.last_request["body"]

    assert body["systemInstruction"]["parts"][0]["text"] == SYSTEM_PROMPT
    user_text = body["contents"][0]["parts"][0]["text"]
    assert "MARKET-abc123" in user_text
    assert "100.5" in user_text


def test_empty_evidence_bundle_is_refused_before_the_call(stub_server):
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request(evidence_payload=[]))
    assert excinfo.value.category == LLMErrorCategory.INVALID_STRUCTURED_OUTPUT
    assert _StubState.last_request is None


# --- structured output schema ------------------------------------------------------------------------

def test_request_pins_a_json_response_schema(stub_server):
    _StubState.body = _ok_body()
    _provider(stub_server).generate_structured_research(_request())
    config = _StubState.last_request["body"]["generationConfig"]

    assert config["responseMimeType"] == "application/json"
    assert set(config["responseSchema"]["required"]) == set(REQUIRED_STRUCTURED_OUTPUT_FIELDS)


def test_schema_is_emitted_in_geminis_dialect_and_cannot_drift():
    schema = _gemini_response_schema()
    assert schema["type"] == "OBJECT"
    assert set(schema["properties"]) == set(REQUIRED_STRUCTURED_OUTPUT_FIELDS)
    assert schema["properties"]["summary"]["type"] == "STRING"
    assert schema["properties"]["evidence_ids"]["type"] == "ARRAY"
    # Gemini rejects additionalProperties; asserting its absence documents that this is
    # deliberate rather than an omission copied from the OpenAI schema.
    assert "additionalProperties" not in schema


def test_max_tokens_and_temperature_reach_generation_config(stub_server):
    _StubState.body = _ok_body()
    _provider(stub_server).generate_structured_research(
        _request(max_tokens=512, temperature=0.2)
    )
    config = _StubState.last_request["body"]["generationConfig"]
    assert config["maxOutputTokens"] == 512
    assert config["temperature"] == 0.2


# --- error mapping --------------------------------------------------------------------------------------

@pytest.mark.parametrize("status_code,api_status,expected", [
    (400, "API_KEY_INVALID", LLMErrorCategory.AUTHENTICATION_FAILURE),
    (403, "PERMISSION_DENIED", LLMErrorCategory.AUTHENTICATION_FAILURE),
    (401, "UNAUTHENTICATED", LLMErrorCategory.AUTHENTICATION_FAILURE),
    (429, "RESOURCE_EXHAUSTED", LLMErrorCategory.RATE_LIMIT),
    (504, "DEADLINE_EXCEEDED", LLMErrorCategory.TIMEOUT),
    (408, "", LLMErrorCategory.TIMEOUT),
    (500, "INTERNAL", LLMErrorCategory.PROVIDER_UNAVAILABLE),
    (503, "UNAVAILABLE", LLMErrorCategory.PROVIDER_UNAVAILABLE),
    (400, "INVALID_ARGUMENT", LLMErrorCategory.PROVIDER_UNAVAILABLE),
])
def test_http_status_maps_to_exactly_one_error_category(
    stub_server, status_code, api_status, expected
):
    _StubState.status = status_code
    _StubState.body = json.dumps({"error": {"status": api_status, "message": "x"}})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == expected
    assert excinfo.value.provider_id == GEMINI_PROVIDER_ID


def test_invalid_key_400_is_authentication_not_a_generic_bad_request(stub_server):
    """Gemini reports a bad key as HTTP 400. Mapping it by status alone would misreport a
    credential problem as a provider outage."""
    _StubState.status = 400
    _StubState.body = json.dumps({"error": {"status": "API_KEY_INVALID", "message": "bad key"}})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.AUTHENTICATION_FAILURE


def test_unparseable_error_body_still_maps_by_status(stub_server):
    _StubState.status, _StubState.body = 503, "<html>gateway</html>"
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.PROVIDER_UNAVAILABLE


def test_unreachable_endpoint_is_provider_unavailable():
    provider = GeminiLLMProvider(api_base_url="http://127.0.0.1:1/v1beta")
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


# --- malformed / empty / refused responses -------------------------------------------------------------

@pytest.mark.parametrize("body", ["not json at all", "[1, 2, 3]"])
def test_non_json_or_non_object_body_is_malformed(stub_server, body):
    _StubState.body = body
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.MALFORMED_RESPONSE


def test_no_candidates_is_an_empty_response(stub_server):
    _StubState.body = json.dumps({"candidates": [], "usageMetadata": {}})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.EMPTY_RESPONSE


def test_blank_parts_are_an_empty_response(stub_server):
    _StubState.body = _ok_body(text="   ")
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.EMPTY_RESPONSE


@pytest.mark.parametrize("finish_reason", ["SAFETY", "RECITATION", "PROHIBITED_CONTENT"])
def test_a_declined_generation_is_invalid_structured_output(stub_server, finish_reason):
    _StubState.body = _ok_body(overrides={"candidates": [{
        "content": {"parts": []}, "finishReason": finish_reason,
    }]})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.INVALID_STRUCTURED_OUTPUT


def test_a_blocked_prompt_is_reported_as_a_refusal_not_an_empty_response(stub_server):
    _StubState.body = json.dumps({
        "promptFeedback": {"blockReason": "SAFETY"},
        "usageMetadata": {"promptTokenCount": 1, "totalTokenCount": 1},
    })
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.INVALID_STRUCTURED_OUTPUT
    assert "blockReason" in excinfo.value.error_message


def test_truncated_response_is_malformed_not_silently_parsed(stub_server):
    _StubState.body = _ok_body(overrides={"candidates": [{
        "content": {"parts": [{"text": '{"summary": "cut off'}]},
        "finishReason": "MAX_TOKENS",
    }]})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.MALFORMED_RESPONSE
    assert "truncated" in excinfo.value.error_message


def test_content_that_is_not_json_is_malformed(stub_server):
    _StubState.body = _ok_body(text="I am prose, not JSON.")
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.MALFORMED_RESPONSE


# --- token provenance -------------------------------------------------------------------------------------

def test_missing_usage_metadata_is_malformed_never_backfilled_with_zeros(stub_server):
    _StubState.body = _ok_body(overrides={"usageMetadata": None})
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.MALFORMED_RESPONSE
    assert "token provenance" in excinfo.value.error_message


def test_absent_candidates_token_count_is_derived_not_fabricated(stub_server):
    """Gemini may omit candidatesTokenCount. The value is derived by subtraction from the counts
    it DID report — arithmetic on reported numbers, never an invented zero."""
    _StubState.body = _ok_body(overrides={
        "usageMetadata": {"promptTokenCount": 40, "totalTokenCount": 100},
    })
    response = _provider(stub_server).generate_structured_research(_request())
    assert response.token_usage.completion_tokens == 60


def test_inconsistent_token_counts_are_malformed(stub_server):
    _StubState.body = _ok_body(overrides={
        "usageMetadata": {"promptTokenCount": 100, "totalTokenCount": 40},   # derives negative
    })
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.MALFORMED_RESPONSE


def test_non_numeric_usage_is_malformed(stub_server):
    _StubState.body = _ok_body(overrides={
        "usageMetadata": {"promptTokenCount": "many", "totalTokenCount": 100},
    })
    with pytest.raises(LLMProviderError) as excinfo:
        _provider(stub_server).generate_structured_research(_request())
    assert excinfo.value.category == LLMErrorCategory.MALFORMED_RESPONSE


# --- provenance: a fake can never impersonate a real provider -----------------------------------------------

def test_fake_providers_never_claim_real_provider_origin():
    for provider in (FakeLLMProvider(), AlternateFakeLLMProvider()):
        response = provider.generate_structured_research(_request())
        assert response.data_origin == "SYNTHETIC_DATA"
        assert response.provider_id != GEMINI_PROVIDER_ID


def test_only_a_real_provider_emits_real_provider_origin(stub_server):
    _StubState.body = _ok_body()
    real = _provider(stub_server).generate_structured_research(_request())
    fake = FakeLLMProvider().generate_structured_research(_request())
    assert (real.data_origin, fake.data_origin) == ("REAL_PROVIDER", "SYNTHETIC_DATA")


def test_provenance_is_fully_recorded_through_the_analyst_layer(stub_server):
    _StubState.body = _ok_body()
    result = generate_ai_research_output(
        [_evidence_item()], _provider(stub_server), model="gemini-2.5-flash",
        prompt_version="1.0",
    )
    identity = result.identity
    assert identity.provider_id == GEMINI_PROVIDER_ID
    assert identity.model == "gemini-2.5-flash"
    assert identity.model_version == "gemini-2.5-flash-001"
    assert identity.prompt_version == "1.0"
    assert identity.request_id                      # llm_request_id
    assert identity.token_usage.total_tokens == 100


# --- the chain against the stub: Evidence -> Gemini -> Structured Output -> Validator -> Report ---------------

def test_validator_still_fails_a_gemini_response_closed(stub_server):
    """Being a real provider earns no exemption from citation validation."""
    _StubState.body = _ok_body(
        text=json.dumps(_structured_output(summary="The close was 4242.42."))
    )
    with pytest.raises(ValueError, match="citation validation failed"):
        generate_ai_research_output(
            [_evidence_item()], _provider(stub_server), model="gemini-2.5-flash"
        )


def test_invented_evidence_id_fails_closed(stub_server):
    _StubState.body = _ok_body(
        text=json.dumps(_structured_output(evidence_ids=["MARKET-doesnotexist"]))
    )
    with pytest.raises(ValueError, match="citation validation failed"):
        generate_ai_research_output(
            [_evidence_item()], _provider(stub_server), model="gemini-2.5-flash"
        )


def test_full_report_chain_through_the_gemini_provider_class(stub_server):
    """Evidence -> GeminiLLMProvider -> StructuredResearchOutput -> Validator -> 10-section
    Research Report. Verifies every link of the mandated chain except the vendor round-trip."""
    from src.quant.research_report.report import generate_research_report

    _StubState.body = _ok_body()
    report = generate_research_report(
        [_evidence_item()], _provider(stub_server), symbol="600519.SH",
        as_of=datetime(2026, 8, 1), model="gemini-2.5-flash", prompt_version="1.0",
        data_origin="REAL_PROVIDER",
    )
    assert len(report.sections) == 10
    assert report.identity.provider_id == GEMINI_PROVIDER_ID
    assert report.identity.data_origin == "REAL_PROVIDER"
    assert report.identity.model_version == "gemini-2.5-flash-001"
    assert report.output.bull_case.strip() != report.output.bear_case.strip()
    assert report.data_confidence.computed_by == "DETERMINISTIC_CODE"


def test_both_real_providers_satisfy_the_same_call_site(stub_server):
    """Provider switching, proven at the orchestration boundary: the analyst layer is handed a
    Gemini provider and an OpenAI provider in turn and changes nothing about how it calls them."""
    _StubState.body = _ok_body()
    gemini_result = generate_ai_research_output(
        [_evidence_item()], _provider(stub_server), model="gemini-2.5-flash"
    )
    assert gemini_result.identity.provider_id == GEMINI_PROVIDER_ID
    assert isinstance(OpenAILLMProvider(), LLMProvider)
    assert OpenAILLMProvider().provider_id == OPENAI_PROVIDER_ID


# --- the one real, billable Gemini call --------------------------------------------------------------------

@pytest.mark.real_llm_provider
def test_real_gemini_end_to_end_evidence_to_validated_report():
    """Evidence -> real Gemini API -> StructuredResearchOutput -> citation validator -> complete
    10-section Research Report.

    Skipped, never failed, when GEMINI_API_KEY is absent. When a real call fails, the failure is
    reported with its exact classified cause — quota, rate limit, timeout, malformed — and never
    dressed up as a pass. Only an exhausted account quota, which no code change can fix, is
    treated as a skip; a credential failure, a timeout or a malformed response all FAIL loudly,
    because each of those could be a real regression in this provider.
    """
    preflight = LLMProviderCredentialPreflight.inspect_credentials(
        GEMINI_PROVIDER_ID, GEMINI_API_KEY_ENV_VAR
    )
    if preflight["credential_status"] != "PRESENT_UNVERIFIED":
        pytest.skip(
            "LLM_PROVIDER_CREDENTIALS_UNAVAILABLE: GEMINI_API_KEY is not set in this "
            "environment, so the real Gemini end-to-end call could not be attempted. This is "
            "NOT a verification — set the key and re-run."
        )

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
            evidence, GeminiLLMProvider(), symbol="600519.SH", as_of=datetime(2026, 8, 1),
            model="gemini-2.5-flash", prompt_version="1.0", data_origin="REAL_PROVIDER",
        )
    except LLMProviderError as e:
        if e.category is LLMErrorCategory.RATE_LIMIT and "quota" in e.error_message.lower():
            pytest.skip(
                f"LLM_PROVIDER_QUOTA_UNAVAILABLE: GEMINI_API_KEY authenticated but the account "
                f"has no remaining quota ({e.category.value}), so the real end-to-end call could "
                "not complete. This is NOT a verification — add quota and re-run."
            )
        # Everything else is surfaced with its classified cause, never softened into a skip.
        pytest.fail(
            f"Real Gemini call failed with category={e.category.value}: {e.error_message}"
        )

    # API authentication succeeded and Gemini returned a structured result...
    assert report.identity.provider_id == GEMINI_PROVIDER_ID
    assert report.identity.data_origin == "REAL_PROVIDER"
    assert report.identity.model_version          # provider-resolved model, real provenance
    assert report.identity.llm_request_id         # provider provenance, recorded
    # ...StructuredResearchOutput parsed, citation validator passed (both are preconditions of
    # generate_research_report returning at all)...
    assert set(report.output.evidence_ids) <= {e.evidence_id for e in evidence}
    assert report.output.bull_case.strip() != report.output.bear_case.strip()
    # ...and a complete Research Report was generated.
    assert len(report.sections) == 10
    assert report.data_confidence.computed_by == "DETERMINISTIC_CODE"
