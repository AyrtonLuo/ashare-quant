"""
openai_provider.py — the first REAL LLM provider implementation.

Implements `LLMProvider` (provider_base.py) against the OpenAI Chat Completions HTTP API using
only the Python standard library — `urllib.request` + `json`. No vendor SDK is installed or
imported, so `requirements.txt` is unchanged; this matches the dependency posture the project
already chose elsewhere (Phase 8R explicitly refused FastAPI/Jinja2/JS tooling for the same
reason). CEO-approved: OpenAI + stdlib, zero new dependencies.

Everything upstream of this file is untouched. `LLMProvider`, `LLMRequest`, `LLMResponse`,
`LLMErrorCategory`, `StructuredResearchOutput`, `validate_citations()` and
`generate_ai_research_output()` are reused exactly as shipped — a real provider was always meant
to be a drop-in for the fakes, and this file proves that by needing no change to any of them.

Security and boundary properties, each structural rather than conventional
==========================================================================
- **The API key is read from the environment and nowhere else.** There is no constructor
  argument, class attribute, or config file that can carry it, so a key cannot be committed to
  the repo by accident. It is placed directly into the request headers and never stored on the
  instance, never included in any exception message, and never logged — this module performs no
  logging at all. `LLMProviderCredentialPreflight` (reused, not reimplemented) decides
  availability, and a missing key raises `CREDENTIALS_UNAVAILABLE` before any socket is opened.
- **The model receives Evidence and nothing else.** The request body is built from
  `request.evidence_payload` only. No tools, no function calling, no web-search or retrieval
  option is sent — the provider is called in plain completion mode, so the model has no
  capability to reach a database, a news API, or the network from inside the call. This is the
  same Evidence Boundary `LLMRequest`'s shape already enforces, preserved at the wire level.
- **Structured output is enforced by schema, not by asking politely.** The request pins
  `response_format` to a strict JSON schema generated from
  `REQUIRED_STRUCTURED_OUTPUT_FIELDS`/`NARRATIVE_TEXT_FIELDS` — the shipped constants, so the
  wire schema cannot drift from the dataclass it must parse into. The response is then still
  put through `parse_structured_output()` upstream: the provider never trusts its own
  transport-level guarantee as a substitute for validation.
- **Every failure resolves to exactly one `LLMErrorCategory`.** Nothing escapes as an
  unclassified exception, and nothing is retried silently or substituted with a default.
- **`data_origin="REAL_PROVIDER"`** is set here and only here. The fakes hard-code
  `SYNTHETIC_DATA`, so a fake can never impersonate a real provider in a persisted artifact.
"""

import json
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.llm.credential import LLMProviderCredentialPreflight
from src.llm.provider_base import (
    LLMErrorCategory,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    LLMTokenUsage,
)
from src.llm.structured_output import (
    NARRATIVE_TEXT_FIELDS,
    REQUIRED_STRUCTURED_OUTPUT_FIELDS,
)

OPENAI_PROVIDER_ID = "openai"
OPENAI_PROVIDER_VERSION = "1.0.0-openai-http"
OPENAI_API_KEY_ENV_VAR = "OPENAI_API_KEY"
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

# The analyst contract, stated to the model. This is belt to the schema's braces: the structural
# guarantees (both cases present, every id real, every number traceable) are enforced downstream
# by parse_structured_output() and validate_citations(), which fail the report closed regardless
# of what any prompt said. Versioned via LLMRequest.prompt_version so a future wording change
# never silently redefines an old report's meaning.
SYSTEM_PROMPT = (
    "You are a securities research analyst. You will be given an Evidence Bundle: a JSON array "
    "of validated, point-in-time-filtered evidence items, each with an evidence_id.\n\n"
    "Rules you must follow exactly:\n"
    "1. Use ONLY the supplied Evidence Bundle. You have no other data source. Never introduce a "
    "fact, figure, date, or event that is not present in the bundle.\n"
    "2. Every number you write must appear in the content of an evidence item you cite. If you "
    "cannot support a figure from the evidence, do not write the figure.\n"
    "3. List in evidence_ids every evidence_id you relied on. Never invent an id.\n"
    "4. If the evidence for a section is absent, say so plainly. Never estimate, extrapolate, or "
    "fill a gap.\n"
    "5. bull_case and bear_case are BOTH mandatory and must present genuinely different "
    "readings. Never produce a single buy/sell verdict, price target, or recommendation.\n"
    "6. If two evidence items conflict, surface the conflict and cite both sides. Never silently "
    "pick one.\n"
    "7. This is research, not investment advice."
)


def _structured_output_json_schema() -> Dict[str, Any]:
    """Built from the shipped schema constants so the wire contract and the dataclass it parses
    into cannot drift apart. `strict` + `additionalProperties: false` + every field required is
    what makes this schema validation rather than a hint."""
    properties: Dict[str, Any] = {
        name: {"type": "string"} for name in NARRATIVE_TEXT_FIELDS
    }
    properties["evidence_ids"] = {"type": "array", "items": {"type": "string"}}
    return {
        "name": "structured_research_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": list(REQUIRED_STRUCTURED_OUTPUT_FIELDS),
            "additionalProperties": False,
        },
    }


class OpenAILLMProvider(LLMProvider):
    """A real, network-calling provider. Constructing one is free and performs no I/O and no
    credential read; the key is looked up per request, so a key rotated between calls is picked
    up and a key is never held on the instance."""

    def __init__(self, model: Optional[str] = None, api_base_url: str = OPENAI_CHAT_COMPLETIONS_URL):
        # `model` here is only a default for callers that do not set LLMRequest.model; the
        # request always wins. `api_base_url` exists so tests can point at a local stub server
        # instead of the internet — it is NOT a way to smuggle a key or a tool in.
        self._default_model = model
        self._api_base_url = api_base_url

    @property
    def provider_id(self) -> str:
        return OPENAI_PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return OPENAI_PROVIDER_VERSION

    def _api_key(self) -> str:
        """Environment only. Raises CREDENTIALS_UNAVAILABLE before any network access, and never
        includes the key (or the absence of one) beyond the preflight's own safe message."""
        report = LLMProviderCredentialPreflight.inspect_credentials(
            self.provider_id, OPENAI_API_KEY_ENV_VAR
        )
        if report["credential_status"] not in ("PRESENT_UNVERIFIED",):
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.CREDENTIALS_UNAVAILABLE, report["message"]
            )
        return os.environ[OPENAI_API_KEY_ENV_VAR]

    def _build_body(self, request: LLMRequest) -> Dict[str, Any]:
        """The user message carries the Evidence Bundle and nothing else. Note the absence of a
        `tools` key: the model is given no capability to call out to anything."""
        body: Dict[str, Any] = {
            "model": request.model or self._default_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Evidence Bundle (JSON):\n"
                        + json.dumps(request.evidence_payload, ensure_ascii=False, sort_keys=True)
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": _structured_output_json_schema(),
            },
        }
        if request.max_tokens is not None:
            body["max_completion_tokens"] = request.max_tokens
        if request.temperature is not None:
            body["temperature"] = request.temperature
        return body

    def _post(self, request: LLMRequest, body: Dict[str, Any]) -> Dict[str, Any]:
        """Performs the HTTP call and maps every transport outcome onto an LLMErrorCategory.
        The key lives only in the local `headers` dict — it is never attached to the exception,
        the instance, or any message this function produces."""
        payload = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key()}",
        }
        http_request = urllib.request.Request(
            self._api_base_url, data=payload, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(http_request, timeout=request.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise self._http_error(e) from None
        except (socket.timeout, TimeoutError) as e:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.TIMEOUT,
                f"request exceeded timeout_seconds={request.timeout_seconds}.",
            ) from None
        except urllib.error.URLError as e:
            # A connection-level failure (DNS, refused, TLS). `e.reason` never contains headers.
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.PROVIDER_UNAVAILABLE,
                f"could not reach the provider endpoint: {e.reason}",
            ) from None

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                f"provider returned a body that is not valid JSON ({e}).",
            ) from None
        if not isinstance(parsed, dict):
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                f"provider returned JSON of type {type(parsed).__name__}, expected an object.",
            )
        return parsed

    def _http_error(self, error: urllib.error.HTTPError) -> LLMProviderError:
        """Maps an HTTP status onto exactly one category. The response body is deliberately NOT
        echoed verbatim into the message beyond a short, bounded excerpt: a provider error body
        is untrusted content, and an unbounded echo is how secrets and injected instructions end
        up in logs."""
        status = error.code
        try:
            detail = error.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            detail = "<no body>"

        if status in (401, 403):
            category = LLMErrorCategory.AUTHENTICATION_FAILURE
        elif status == 429:
            category = LLMErrorCategory.RATE_LIMIT
        elif status in (408, 504):
            category = LLMErrorCategory.TIMEOUT
        else:
            category = LLMErrorCategory.PROVIDER_UNAVAILABLE
        return LLMProviderError(
            self.provider_id, category, f"HTTP {status} from provider: {detail}"
        )

    def _extract_content(self, parsed: Dict[str, Any]) -> str:
        choices = parsed.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.EMPTY_RESPONSE,
                "provider returned no choices.",
            )
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                "provider choice contains no message object.",
            )
        # An explicit refusal is a valid, well-formed API response that carries no research
        # output — it is neither malformed nor empty, so it gets its own accurate category.
        if message.get("refusal"):
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.INVALID_STRUCTURED_OUTPUT,
                "provider refused to produce the structured output.",
            )
        if choices[0].get("finish_reason") == "length":
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                "provider response was truncated by the token limit; the structured output is "
                "incomplete and will not be parsed.",
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.EMPTY_RESPONSE,
                "provider returned an empty message content.",
            )
        return content

    def _token_usage(self, parsed: Dict[str, Any]) -> LLMTokenUsage:
        """Token usage is provider provenance the identity records; a response without it is
        treated as malformed rather than back-filled with zeros, which would be a fabricated
        provenance value."""
        usage = parsed.get("usage")
        if not isinstance(usage, dict):
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                "provider response carries no usage block; token provenance cannot be recorded.",
            )
        try:
            return LLMTokenUsage(
                prompt_tokens=int(usage["prompt_tokens"]),
                completion_tokens=int(usage["completion_tokens"]),
                total_tokens=int(usage["total_tokens"]),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                f"provider usage block is incomplete or non-numeric ({e}).",
            ) from None

    def generate_structured_research(self, request: LLMRequest) -> LLMResponse:
        if not request.evidence_payload:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.INVALID_STRUCTURED_OUTPUT,
                "refusing to call the provider with an empty Evidence Bundle.",
            )

        started = time.monotonic()
        parsed = self._post(request, self._build_body(request))
        latency = time.monotonic() - started

        content = self._extract_content(parsed)
        try:
            raw_structured_output = json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                f"provider message content is not valid JSON ({e}).",
            ) from None
        if not isinstance(raw_structured_output, dict):
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                f"structured output is a {type(raw_structured_output).__name__}, expected an "
                "object.",
            )

        return LLMResponse(
            request_id=request.request_id,
            provider_id=self.provider_id,
            model=request.model,
            # The resolved snapshot the provider actually served (e.g. a dated model id) —
            # genuine provider-reported provenance, never the requested alias echoed back.
            model_version=parsed.get("model"),
            raw_structured_output=raw_structured_output,
            token_usage=self._token_usage(parsed),
            latency_seconds=latency,
            received_at=datetime.now(),
            data_origin="REAL_PROVIDER",
        )
