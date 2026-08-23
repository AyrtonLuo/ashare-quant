"""
provider_base.py — LLM Provider Abstract Interface & shared request/response/error types.

CEO Directive "LLM Provider Architecture & Implementation". Mirrors the exact established
pattern already used for data providers (src/data/providers/base.py: UnifiedDataProvider,
NewsAnnouncementProvider, ProviderError) — a provider_id/provider_version property pair plus
one abstract method, so `OpenAI ↔ Claude ↔ Gemini` can be swapped by implementing this same ABC
without changing anything upstream (Research Analyst, §ResearchAnalyst below).

The Research Analyst layer (research_analyst.py) is the ONLY caller of `LLMProvider.
generate_structured_research()`. No vendor SDK is imported anywhere in this package: the real
provider (openai_provider.py) speaks the vendor's HTTP API using only the standard library, so
`requirements.txt` carries no LLM dependency.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class LLMErrorCategory(str, Enum):
    """Every provider failure must resolve to exactly one of these — never an unclassified
    exception. Matches the directive's explicit item 6 checklist."""
    TIMEOUT = "TIMEOUT"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    RATE_LIMIT = "RATE_LIMIT"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_STRUCTURED_OUTPUT = "INVALID_STRUCTURED_OUTPUT"
    CREDENTIALS_UNAVAILABLE = "CREDENTIALS_UNAVAILABLE"


class LLMProviderError(Exception):
    """Mirrors src/data/providers/base.py's ProviderError exactly, with an added explicit
    error_category (the data-provider ProviderError has no such field — LLM failures are more
    varied and the directive explicitly requires an unambiguous status for every failure mode)."""
    def __init__(self, provider_id: str, category: LLMErrorCategory, error_message: str):
        self.provider_id = provider_id
        self.category = category
        self.error_message = error_message
        super().__init__(f"[{provider_id}] {category.value}: {error_message}")


@dataclass(frozen=True)
class LLMTokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def __post_init__(self):
        if self.prompt_tokens < 0 or self.completion_tokens < 0 or self.total_tokens < 0:
            raise ValueError("FAIL CLOSED: token usage counts must not be negative.")


@dataclass(frozen=True)
class LLMRequest:
    """What gets sent to a provider. `evidence_payload` is the ONLY content payload — there is
    no field here through which a database handle, API client, or search capability could be
    passed; the Evidence Boundary (directive item 3) is enforced by this shape, not by convention."""
    request_id: str
    model: str
    prompt_version: str
    evidence_bundle_hash: str          # binds this request to a specific, already-hashed bundle
    evidence_payload: List[Dict[str, Any]]  # canonical, serialized EvidenceItem records only
    timeout_seconds: float = 60.0
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

    def __post_init__(self):
        if not self.request_id:
            raise ValueError("FAIL CLOSED: LLMRequest.request_id must not be empty.")
        if not self.model:
            raise ValueError("FAIL CLOSED: LLMRequest.model must not be empty.")
        if self.timeout_seconds <= 0:
            raise ValueError(f"FAIL CLOSED: invalid timeout_seconds {self.timeout_seconds}.")


@dataclass(frozen=True)
class LLMResponse:
    request_id: str                     # echoes LLMRequest.request_id — correlation, not trust
    provider_id: str
    model: str
    model_version: Optional[str]        # "if the provider supplies it" — directive item 8
    raw_structured_output: Dict[str, Any]   # parsed JSON, NOT yet schema-validated
    token_usage: LLMTokenUsage
    latency_seconds: float
    received_at: datetime
    data_origin: str = "SYNTHETIC_DATA"  # REAL_PROVIDER | SYNTHETIC_DATA — same project vocabulary

    def __post_init__(self):
        if self.latency_seconds < 0:
            raise ValueError(f"FAIL CLOSED: invalid latency_seconds {self.latency_seconds}.")


class LLMProvider(ABC):
    """One abstract method, same shape as UnifiedDataProvider/NewsAnnouncementProvider.
    Implementations: openai_provider.py (real, network-calling, data_origin=REAL_PROVIDER) and
    fake_provider.py (two deterministic test doubles, permanently data_origin=SYNTHETIC_DATA, so
    a fake can never impersonate a real provider in a persisted artifact)."""

    @property
    @abstractmethod
    def provider_id(self) -> str: pass

    @property
    @abstractmethod
    def provider_version(self) -> str: pass

    @abstractmethod
    def generate_structured_research(self, request: LLMRequest) -> LLMResponse:
        """Must raise LLMProviderError (with an explicit LLMErrorCategory) on any failure —
        never return a partial/guessed LLMResponse, never silently substitute a default."""
        pass
