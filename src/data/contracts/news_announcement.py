"""
news_announcement.py — Canonical News / Company Announcement Contract.

AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §3.1 (CEO-approved design), now implemented.
Modeled directly on corporate_action.py's established PIT pattern (available_at/received_at),
not a new convention. Every field required for evidence traceability per the CEO's explicit
directive: source, source_id, symbol, title, published_at, received_at, retrieved_at, provenance.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class NewsAnnouncementContract:
    source_id: str            # provider's own unique id for this item — dedup/lineage anchor
    source: str                # named source/wire, e.g. "上交所公告", "巨潮资讯网" — never "unknown"
    item_type: str              # "NEWS" | "COMPANY_ANNOUNCEMENT" | "REGULATORY_FILING"
    symbols: List[str]         # explicit symbol mentions only — never inferred by any downstream reader
    title: str
    body_summary: str          # a stored excerpt/summary captured at ingest — never paraphrased later
    source_url: Optional[str]

    published_at: datetime     # when the source published it (event time)

    # PIT visibility. Mirrors corporate_action.py's contract exactly — NOT derived from
    # published_at as a substitute for legal/system availability, which are separate concepts.
    available_at: Optional[datetime] = None   # when the system could legally treat this as known
    received_at: Optional[datetime] = None    # when the payload arrived in this system
    retrieved_at: Optional[datetime] = None   # when THIS fetch/adapter call retrieved it — may
                                               # differ from received_at on a re-fetch of an
                                               # already-ingested historical archive

    relevance_score: float = 0.0        # DETERMINISTIC, rule-based (never an AI/LLM judgment)
    duplicate_cluster_id: Optional[str] = None  # deterministic dedup key, set by the adapter/
                                                 # assembly layer — never computed by an LLM

    quality_status: str = "VALID"       # "VALID" | "SUSPECT"
    # Provenance: REAL_PROVIDER | LOCAL_PRODUCTION_VERIFICATION_DATA | GOLDEN_DATASET |
    # SYNTHETIC_DATA — the same 4-tag vocabulary used project-wide, not a new one. Defaults to
    # SYNTHETIC_DATA (fail-closed); only a code path that actually parsed a live, audited news
    # provider response may set REAL_PROVIDER.
    data_origin: str = "SYNTHETIC_DATA"

    def __post_init__(self):
        # Structural (Contract-stage) invariants only — temporal/business validation (future
        # timestamps, missing PIT fields, malformed content) belongs to DataTrustGate
        # (Validation stage), kept deliberately separate per the directive's own pipeline stages.
        if not self.source_id:
            raise ValueError("FAIL CLOSED: NewsAnnouncementContract.source_id must not be empty.")
        if not self.source:
            raise ValueError("FAIL CLOSED: NewsAnnouncementContract.source must not be empty.")
        if not self.title:
            raise ValueError("FAIL CLOSED: NewsAnnouncementContract.title must not be empty.")
        if not self.symbols:
            raise ValueError(
                "FAIL CLOSED: NewsAnnouncementContract.symbols must not be empty — market-wide, "
                "no-symbol items are out of scope for this phase (see the architecture proposal)."
            )
        if self.item_type not in ("NEWS", "COMPANY_ANNOUNCEMENT", "REGULATORY_FILING"):
            raise ValueError(f"FAIL CLOSED: unknown item_type '{self.item_type}'.")
