"""
gemini_provider.py — real Google Gemini LLM provider.

Implements the SAME `LLMProvider` ABC as `openai_provider.py`, using only the Python standard
library (`urllib.request` + `json`) against the official Gemini REST API. No `google-generativeai`
SDK is installed or imported, so `requirements.txt` stays unchanged — the same dependency posture
the OpenAI provider already established.

Nothing upstream is refactored. `LLMProvider`, `LLMRequest`, `LLMResponse`, `LLMErrorCategory`,
`StructuredResearchOutput`, `parse_structured_output()`, `validate_citations()` and
`generate_ai_research_output()` are reused exactly as shipped, and `OpenAILLMProvider` is left
untouched and fully functional beside this one — swapping vendors is an implementation choice at
the call site, never an interface change.

Where Gemini genuinely differs from OpenAI, and why it is handled rather than glossed over
===========================================================================================
- **Model lives in the URL path**, not the body: `…/v1beta/models/{model}:generateContent`.
- **Auth is the `x-goog-api-key` HEADER.** Gemini also accepts `?key=` in the query string; that
  form is deliberately NOT used here — a secret in a URL leaks into proxy logs, browser history
  and error strings in a way a header does not.
- **Schema dialect differs**: Gemini's `responseSchema` uses uppercase type names and does not
  accept `additionalProperties`, so the schema is emitted in Gemini's dialect while still being
  generated from the same shipped `REQUIRED_STRUCTURED_OUTPUT_FIELDS` / `NARRATIVE_TEXT_FIELDS`
  constants — the wire contract cannot drift from the dataclass it parses into.
- **An invalid API key returns HTTP 400**, not 401. Mapping 400 blindly to
  `PROVIDER_UNAVAILABLE` would misreport a credential problem as an outage, so the error body's
  status is inspected and `API_KEY_INVALID` / `PERMISSION_DENIED` map to
  `AUTHENTICATION_FAILURE`.
- **Token usage names differ** (`usageMetadata.promptTokenCount` etc.), and Gemini may omit
  `candidatesTokenCount`. When it does, the value is derived by subtraction from the two counts
  the provider *did* report — arithmetic on reported numbers, never a fabricated zero.

Security and boundary properties, identical in kind to the OpenAI provider
==========================================================================
- The API key is read from `GEMINI_API_KEY` and nowhere else. No constructor argument, class
  attribute, config file or persisted artifact can carry it; it is never stored on the instance,
  never included in an exception message, and never logged — this module performs no logging.
  A missing key raises `CREDENTIALS_UNAVAILABLE` before any socket is opened.
- The model receives Evidence and nothing else. The body is built from
  `request.evidence_payload` only, and carries no `tools`, no `functionDeclarations`, and no
  `googleSearch`/`googleSearchRetrieval` grounding block — so the model has no capability to
  reach a database, a news API, a market API, or the web from inside the call.
- Every failure resolves to exactly one `LLMErrorCategory`; nothing is retried silently or
  substituted with a default, and nothing ever falls back to a synthetic narrative.
- `data_origin="REAL_PROVIDER"` — the fakes hard-code `SYNTHETIC_DATA`, so a fake can never
  impersonate this provider in a persisted artifact.
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

GEMINI_PROVIDER_ID = "gemini"
GEMINI_PROVIDER_VERSION = "1.0.0-gemini-rest"
GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Byte-identical in intent to the OpenAI provider's prompt: the structural guarantees (both cases
# present, every id real, every number traceable) are enforced downstream by
# parse_structured_output() and validate_citations() regardless of what any prompt said. Kept as
# its own constant rather than imported from openai_provider, so neither vendor's prompt can be
# changed by editing the other's.
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

# Gemini finish reasons that mean "the model declined", as opposed to "the model was cut off".
# A decline is a well-formed response carrying no research output, so it gets the accurate
# category rather than being lumped in with malformed transport.
_REFUSAL_FINISH_REASONS = frozenset({
    "SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY",
})
# Error statuses Gemini returns for a credential problem, including the 400 case that would
# otherwise be misclassified as a generic bad request.
_AUTH_ERROR_STATUSES = frozenset({"API_KEY_INVALID", "PERMISSION_DENIED", "UNAUTHENTICATED"})


def _gemini_response_schema() -> Dict[str, Any]:
    """The same 10-field contract as everywhere else, expressed in Gemini's schema dialect
    (uppercase type names, `propertyOrdering`, no `additionalProperties`). Generated from the
    shipped constants so it cannot drift from `StructuredResearchOutput`."""
    properties: Dict[str, Any] = {name: {"type": "STRING"} for name in NARRATIVE_TEXT_FIELDS}
    properties["evidence_ids"] = {"type": "ARRAY", "items": {"type": "STRING"}}
    return {
        "type": "OBJECT",
        "properties": properties,
        "required": list(REQUIRED_STRUCTURED_OUTPUT_FIELDS),
        "propertyOrdering": list(REQUIRED_STRUCTURED_OUTPUT_FIELDS),
    }


class GeminiLLMProvider(LLMProvider):
    """A real, network-calling provider. Constructing one performs no I/O and reads no
    credential; the key is looked up per request, so a rotated key is picked up and no key is
    ever held on the instance."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_base_url: str = GEMINI_API_BASE_URL,
    ):
        # `model` is only a default for callers that do not set LLMRequest.model; the request
        # always wins. `api_base_url` exists so tests can point at a local stub instead of the
        # internet — it is NOT a way to smuggle in a key or a tool.
        self._default_model = model
        self._api_base_url = api_base_url.rstrip("/")

    @property
    def provider_id(self) -> str:
        return GEMINI_PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return GEMINI_PROVIDER_VERSION

    def _api_key(self) -> str:
        """Environment only. Raises CREDENTIALS_UNAVAILABLE before any network access; the
        preflight's message never contains the key value."""
        report = LLMProviderCredentialPreflight.inspect_credentials(
            self.provider_id, GEMINI_API_KEY_ENV_VAR
        )
        if report["credential_status"] != "PRESENT_UNVERIFIED":
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.CREDENTIALS_UNAVAILABLE, report["message"]
            )
        return os.environ[GEMINI_API_KEY_ENV_VAR]

    def _endpoint(self, model: str) -> str:
        """Gemini puts the model in the path. The key is NOT appended as a `?key=` query
        parameter — it travels in a header, so it cannot leak through a URL."""
        return f"{self._api_base_url}/models/{model}:generateContent"

    def _build_body(self, request: LLMRequest) -> Dict[str, Any]:
        """The user turn carries the Evidence Bundle and nothing else. Note the absence of
        `tools`, `functionDeclarations` and any grounding/search block: the model is given no
        capability to call out to anything."""
        generation_config: Dict[str, Any] = {
            "responseMimeType": "application/json",
            "responseSchema": _gemini_response_schema(),
        }
        if request.max_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_tokens
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature

        return {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{
                "role": "user",
                "parts": [{
                    "text": (
                        "Evidence Bundle (JSON):\n"
                        + json.dumps(request.evidence_payload, ensure_ascii=False, sort_keys=True)
                    )
                }],
            }],
            "generationConfig": generation_config,
        }

    def _post(self, request: LLMRequest, body: Dict[str, Any]) -> Dict[str, Any]:
        """Performs the HTTP call and maps every transport outcome onto an LLMErrorCategory. The
        key exists only inside the local `headers` dict — never on the instance, never attached
        to an exception, never in any message this function produces."""
        model = request.model or self._default_model
        payload = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key(),
        }
        http_request = urllib.request.Request(
            self._endpoint(model), data=payload, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(http_request, timeout=request.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise self._http_error(e) from None
        except (socket.timeout, TimeoutError):
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.TIMEOUT,
                f"request exceeded timeout_seconds={request.timeout_seconds}.",
            ) from None
        except urllib.error.URLError as e:
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
        """Maps an HTTP status onto exactly one category. Gemini reports an invalid key as HTTP
        400, so the body's `error.status` is inspected before falling back to the status code —
        otherwise a credential problem would be reported as a provider outage. The body is
        echoed only as a short bounded excerpt: a provider error body is untrusted content, and
        an unbounded echo is how secrets and injected instructions end up in logs."""
        status_code = error.code
        try:
            body_text = error.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        detail = body_text[:200] if body_text else "<no body>"

        api_status = ""
        try:
            payload = json.loads(body_text)
            if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
                api_status = str(payload["error"].get("status", ""))
        except (json.JSONDecodeError, TypeError, ValueError):
            api_status = ""

        if api_status in _AUTH_ERROR_STATUSES or status_code in (401, 403):
            category = LLMErrorCategory.AUTHENTICATION_FAILURE
        elif api_status == "RESOURCE_EXHAUSTED" or status_code == 429:
            category = LLMErrorCategory.RATE_LIMIT
        elif status_code in (408, 504) or api_status == "DEADLINE_EXCEEDED":
            category = LLMErrorCategory.TIMEOUT
        else:
            category = LLMErrorCategory.PROVIDER_UNAVAILABLE
        return LLMProviderError(
            self.provider_id, category, f"HTTP {status_code} from provider: {detail}"
        )

    def _extract_text(self, parsed: Dict[str, Any]) -> str:
        """Gemini returns candidates -> content -> parts[], where the parts are concatenated to
        form the message. A prompt-level block (`promptFeedback.blockReason`) arrives with no
        candidates at all, and is reported as a refusal rather than as an empty response."""
        block_reason = ""
        feedback = parsed.get("promptFeedback")
        if isinstance(feedback, dict):
            block_reason = str(feedback.get("blockReason", ""))
        if block_reason:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.INVALID_STRUCTURED_OUTPUT,
                f"provider blocked the prompt (blockReason={block_reason}).",
            )

        candidates = parsed.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.EMPTY_RESPONSE,
                "provider returned no candidates.",
            )
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                "provider candidate is not an object.",
            )

        finish_reason = str(candidate.get("finishReason", ""))
        if finish_reason in _REFUSAL_FINISH_REASONS:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.INVALID_STRUCTURED_OUTPUT,
                f"provider declined to produce the structured output "
                f"(finishReason={finish_reason}).",
            )
        if finish_reason == "MAX_TOKENS":
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                "provider response was truncated by the token limit; the structured output is "
                "incomplete and will not be parsed.",
            )

        content = candidate.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                "provider candidate carries no content parts.",
            )
        text = "".join(
            part["text"] for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
        if not text.strip():
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.EMPTY_RESPONSE,
                "provider returned empty content parts.",
            )
        return text

    def _token_usage(self, parsed: Dict[str, Any]) -> LLMTokenUsage:
        """Token usage is provider provenance the identity records, so a response without it is
        treated as malformed rather than back-filled with zeros. Gemini may omit
        `candidatesTokenCount`; when it does, the value is DERIVED by subtraction from the two
        counts the provider did report — arithmetic on reported numbers, not a fabricated value.
        A derivation that comes out negative means the counts disagree, which is malformed."""
        usage = parsed.get("usageMetadata")
        if not isinstance(usage, dict):
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                "provider response carries no usageMetadata; token provenance cannot be "
                "recorded.",
            )
        try:
            prompt_tokens = int(usage["promptTokenCount"])
            total_tokens = int(usage["totalTokenCount"])
            completion_tokens = (
                int(usage["candidatesTokenCount"]) if "candidatesTokenCount" in usage
                else total_tokens - prompt_tokens
            )
        except (KeyError, TypeError, ValueError) as e:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                f"provider usageMetadata is incomplete or non-numeric ({e}).",
            ) from None

        try:
            return LLMTokenUsage(
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
        except ValueError as e:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                f"provider usageMetadata counts are inconsistent ({e}).",
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

        text = self._extract_text(parsed)
        try:
            raw_structured_output = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMProviderError(
                self.provider_id, LLMErrorCategory.MALFORMED_RESPONSE,
                f"provider content is not valid JSON ({e}).",
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
            # The resolved model the provider actually served — genuine provider-reported
            # provenance, never the requested alias echoed back.
            model_version=parsed.get("modelVersion"),
            raw_structured_output=raw_structured_output,
            token_usage=self._token_usage(parsed),
            latency_seconds=latency,
            received_at=datetime.now(),
            data_origin="REAL_PROVIDER",
        )
