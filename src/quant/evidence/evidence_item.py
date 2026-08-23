"""
evidence_item.py — Evidence Layer: EvidenceItem and deterministic assembly functions.

AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §5/§6 (CEO-approved design), now implemented
for the Contract -> Validation -> PIT -> Provenance -> Evidence stages only. No AI/LLM synthesis
is implemented here or anywhere in this phase — see the module docstring's own scope note below.

Structural guarantees this module exists to provide:
- Every EvidenceItem has a unique evidence_id and an explicit provenance (data_origin).
- `kind` is constrained to "FACT" | "MODEL_OUTPUT" — "AI_INTERPRETATION" is not a valid kind,
  by construction. AI Interpretation is a report's OUTPUT, never an Evidence Layer INPUT — this
  is what "AI interpretation 不能重新成为 Evidence" means concretely: the type system forecloses
  it, not merely a convention.
- Assembly functions take already-validated, already-PIT-filtered Contracts and never expose a
  raw provider response type in their return value — "AI 不能直接读取 raw API response" is
  satisfied by construction: nothing downstream of these functions ever sees anything but
  EvidenceItem.
- The full Evidence Bundle (List[EvidenceItem] for one report) is canonically hashed, the same
  compute_canonical_sha256 function used everywhere else in this codebase — not a new hashing
  scheme.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.contracts.news_announcement import NewsAnnouncementContract
from src.data.contracts.derived import DerivedDataContract
from src.data.validation.pit_gate import PITGate
from src.data.validation.gate import DataTrustGate
from src.quant.reproducibility.canonical import compute_canonical_sha256

VALID_EVIDENCE_KINDS = ("FACT", "MODEL_OUTPUT")
VALID_EVIDENCE_CATEGORIES = (
    "TECHNICAL", "FUNDAMENTAL", "QUANT_FACTOR", "MARKET", "NEWS", "ANNOUNCEMENT",
    "CORPORATE_ACTION", "RISK",
)


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    category: str            # one of VALID_EVIDENCE_CATEGORIES
    kind: str                 # "FACT" | "MODEL_OUTPUT" — never "AI_INTERPRETATION"
    content: Any               # a number, short structured record, or short text excerpt
    event_date: Optional[str]  # when the underlying fact/event occurred
    available_at: Optional[datetime]
    received_at: Optional[datetime]
    source: str                 # which system/provider produced this item, by name
    data_origin: str            # REAL_PROVIDER | LOCAL_PRODUCTION_VERIFICATION_DATA |
                                 # GOLDEN_DATASET | SYNTHETIC_DATA — same project-wide vocabulary

    def __post_init__(self):
        if self.kind not in VALID_EVIDENCE_KINDS:
            raise ValueError(
                f"FAIL CLOSED: invalid EvidenceItem.kind '{self.kind}' — must be one of "
                f"{VALID_EVIDENCE_KINDS}. AI Interpretation is never a valid Evidence kind."
            )
        if self.category not in VALID_EVIDENCE_CATEGORIES:
            raise ValueError(f"FAIL CLOSED: invalid EvidenceItem.category '{self.category}'.")
        if not self.evidence_id:
            raise ValueError("FAIL CLOSED: EvidenceItem.evidence_id must not be empty.")
        if not self.source:
            raise ValueError("FAIL CLOSED: EvidenceItem.source must not be empty.")


def _make_evidence_id(category: str, content_repr: Any) -> str:
    """Deterministic, content-derived, collision-resistant id — never a mutable counter."""
    digest = compute_canonical_sha256(content_repr)
    return f"{category}-{digest[:12]}"


def assemble_market_evidence(
    symbol: str, contracts: List[MarketDataContract],
) -> List[EvidenceItem]:
    """Each contract must independently pass DataTrustGate.validate_market_data() — a contract
    that fails validation is EXCLUDED, never silently included with a default/guessed value."""
    items = []
    for c in contracts:
        if c.symbol != symbol:
            raise ValueError(f"FAIL CLOSED: MarketDataContract for '{c.symbol}' does not match requested symbol '{symbol}'.")
        is_valid, errors = DataTrustGate.validate_market_data(c)
        if not is_valid:
            continue
        content = {
            "trading_date": c.trading_date, "open": c.open_price, "high": c.high_price,
            "low": c.low_price, "close": c.close_price, "volume": c.volume,
        }
        items.append(EvidenceItem(
            evidence_id=_make_evidence_id("MARKET", {"symbol": symbol, **content}),
            category="MARKET", kind="FACT", content=content, event_date=c.trading_date,
            available_at=None, received_at=None, source="MarketDataContract",
            data_origin=c.data_origin,
        ))
    return items


def assemble_fundamental_evidence(
    symbol: str, contracts: List[FundamentalDataContract], as_of: datetime,
) -> List[EvidenceItem]:
    """Validation (DataTrustGate) then PIT filter (the EXISTING PITGate.filter_pit_fundamentals()
    — not reimplemented), matching the directive's stated pipeline order exactly."""
    checked = []
    for c in contracts:
        if c.symbol != symbol:
            raise ValueError(f"FAIL CLOSED: FundamentalDataContract for '{c.symbol}' does not match requested symbol '{symbol}'.")
        is_valid, errors = DataTrustGate.validate_fundamental_data(c)
        if is_valid:
            checked.append(c)
    visible = PITGate.filter_pit_fundamentals(checked, as_of)
    items = []
    for c in visible:
        content = {
            "report_date": c.report_date, "pe_ttm": c.pe_ttm, "pb": c.pb,
            "dividend_yield_ttm": c.dividend_yield_ttm, "roe": c.roe,
        }
        items.append(EvidenceItem(
            evidence_id=_make_evidence_id("FUNDAMENTAL", {"symbol": symbol, **content}),
            category="FUNDAMENTAL", kind="FACT", content=content, event_date=c.report_date,
            available_at=c.available_at, received_at=c.received_at,
            source="FundamentalDataContract", data_origin=c.data_origin,
        ))
    return items


def _normalize_title(title: str) -> str:
    return "".join(ch for ch in title.lower().strip() if ch.isalnum() or ch.isspace())


def detect_duplicate_news(items: List[NewsAnnouncementContract]) -> List[NewsAnnouncementContract]:
    """Deterministic dedup — never AI-judged. Cluster key: normalized title + item_type +
    sorted(symbols) + publish date. Returns a NEW list (contracts are frozen) with
    duplicate_cluster_id populated on every item that shares a cluster with at least one other
    item; singletons get duplicate_cluster_id=None (nothing to link)."""
    from dataclasses import replace

    clusters: Dict[str, List[int]] = {}
    for idx, item in enumerate(items):
        key = compute_canonical_sha256({
            "title": _normalize_title(item.title), "item_type": item.item_type,
            "symbols": sorted(item.symbols), "date": item.published_at.strftime("%Y-%m-%d"),
        })[:16]
        clusters.setdefault(key, []).append(idx)

    result = list(items)
    for key, indices in clusters.items():
        if len(indices) > 1:
            for idx in indices:
                result[idx] = replace(result[idx], duplicate_cluster_id=key)
    return result


def assemble_news_evidence(
    symbol: str, raw_items: List[NewsAnnouncementContract], as_of: datetime,
) -> List[EvidenceItem]:
    """Full News chain, matching the directive's own stated pipeline order exactly: Contract
    (already NewsAnnouncementContract by the time this function is called) -> dedup -> DataTrustGate
    Validation -> PITGate PIT filter -> Evidence. (Validation and PIT independently exclude
    overlapping-but-not-identical problems — a validation failure is a data-quality problem, a
    PIT failure is a temporal-visibility problem — running Validation first, as the directive's
    diagram states, means a not-yet-PIT-visible item that is ALSO malformed is still caught and
    reported as a validation failure, not silently absorbed into "just not visible yet.")
    Produces one representative EvidenceItem per duplicate cluster (earliest received_at), with
    a `suppressed_duplicate_count` recorded on the representative's content — never silently
    dropped, matching this project's anti-fabrication "declare, never silently discard" rule.
    Conflicting items (same cluster is NOT the same as conflicting — two independent items about
    the same symbol with contradictory claims are NOT deduped, both are kept as separate
    EvidenceItems; conflict surfacing is a report-generation-time concern, not an assembly-time
    one, since only the (future) AI step can articulate what the conflict IS)."""
    deduped = detect_duplicate_news(raw_items)

    gate_passed = []
    for item in deduped:
        if symbol not in item.symbols:
            raise ValueError(f"FAIL CLOSED: news item '{item.source_id}' does not mention requested symbol '{symbol}'.")
        is_valid, errors = DataTrustGate.validate_news_announcement(item)
        if not is_valid:
            continue
        gate_passed.append(item)

    validated = PITGate.filter_pit_news_announcements(gate_passed, as_of)

    by_cluster: Dict[Optional[str], List[NewsAnnouncementContract]] = {}
    for item in validated:
        by_cluster.setdefault(item.duplicate_cluster_id, []).append(item)

    evidence_items = []
    for cluster_id, cluster_items in by_cluster.items():
        if cluster_id is None:
            representatives = cluster_items  # singletons — each is its own representative
            suppressed_counts = [0] * len(cluster_items)
        else:
            cluster_items.sort(key=lambda i: i.received_at or datetime.max)
            representatives = [cluster_items[0]]
            suppressed_counts = [len(cluster_items) - 1]

        for rep, suppressed in zip(representatives, suppressed_counts):
            content = {
                "title": rep.title, "source": rep.source, "item_type": rep.item_type,
                "body_summary": rep.body_summary, "relevance_score": rep.relevance_score,
                "suppressed_duplicate_count": suppressed,
            }
            evidence_items.append(EvidenceItem(
                evidence_id=_make_evidence_id("NEWS", {"symbol": symbol, "source_id": rep.source_id}),
                category="ANNOUNCEMENT" if rep.item_type != "NEWS" else "NEWS",
                kind="FACT", content=content,
                event_date=rep.published_at.strftime("%Y-%m-%d"),
                available_at=rep.available_at, received_at=rep.received_at,
                source=rep.source, data_origin=rep.data_origin,
            ))
    return evidence_items


def assemble_technical_evidence(
    symbol: str, contracts: List[DerivedDataContract],
) -> List[EvidenceItem]:
    """Only contracts with warm_up_satisfied=True and passing DataTrustGate become Evidence — an
    INSUFFICIENT_WARM_UP record is a legitimate, informative non-inclusion, not an error, and is
    simply skipped here (its absence from the Evidence Bundle IS the signal, not a hidden gap)."""
    items = []
    for c in contracts:
        if c.symbol != symbol:
            raise ValueError(f"FAIL CLOSED: technical indicator for '{c.symbol}' does not match requested symbol '{symbol}'.")
        if not c.warm_up_satisfied:
            continue
        is_valid, errors = DataTrustGate.validate_technical_indicator(c)
        if not is_valid:
            continue
        content = {
            "indicator": c.metric_name, "value": c.calculated_value, "parameters": c.parameters,
            "input_price_basis": c.input_price_basis, "lookback_window": c.lookback_window,
        }
        items.append(EvidenceItem(
            evidence_id=_make_evidence_id("TECHNICAL", {"symbol": symbol, **content, "date": c.effective_date}),
            category="TECHNICAL", kind="MODEL_OUTPUT", content=content, event_date=c.effective_date,
            available_at=None, received_at=None, source="technical.indicators (LOCAL_CANONICAL_CALCULATION)",
            data_origin=c.data_origin,
        ))
    return items


def compute_evidence_bundle_hash(items: List[EvidenceItem]) -> str:
    """Canonical hash over the full, ordered Evidence Bundle — the same compute_canonical_sha256
    function used for result_hash/input_hash/manifest hashes everywhere else in this codebase."""
    payload = [
        {
            "evidence_id": i.evidence_id, "category": i.category, "kind": i.kind,
            "content": i.content, "event_date": i.event_date, "source": i.source,
            "data_origin": i.data_origin,
        }
        for i in items
    ]
    return compute_canonical_sha256(payload)
