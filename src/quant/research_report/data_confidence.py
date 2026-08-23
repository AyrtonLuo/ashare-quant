"""
data_confidence.py — Deterministic evidence-conflict detection and the computed Data Confidence
metric (AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §7 section 9, §3.3).

Two hard rules this module exists to enforce:

1. **Data Confidence is a COMPUTED metric, never an AI self-rating.** Nothing here calls, imports,
   or is influenced by an LLM. Every sub-score is exposed on the result (`components`), so the
   final number is auditable rather than a black box — a reader can re-derive it by hand.
2. **Conflicts are detected by code, never adjudicated by the model.** `detect_evidence_conflicts()`
   surfaces disagreements; it never picks a winner, never drops a side, and never resolves.

Disclosed limitation, stated rather than glossed over: deterministic conflict detection covers
the structurally decidable case — two evidence items describing the SAME identified thing at the
SAME date with DIFFERENT values (two providers disagreeing on a close price, a revised
fundamental). It cannot detect a *semantic* contradiction between two free-text news items (the
proposal §3.3 "M&A rumour later denied" case): that is not deterministically decidable, so it is
not claimed here. Surfacing that class of conflict remains the AI's narrative contract (§6),
and the report marks conflict detection's scope explicitly so a reader never mistakes
"no conflicts detected" for "no conflicts exist".
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.quant.evidence.evidence_item import EvidenceItem
from src.quant.reproducibility.canonical import compute_canonical_sha256

# Categories a complete §7 report expects to draw on. NEWS is satisfied by either NEWS or
# ANNOUNCEMENT evidence — they are one report section (§7 #5), split into two categories only at
# the Evidence Layer.
REPORT_EVIDENCE_CATEGORIES: Tuple[str, ...] = (
    "MARKET", "TECHNICAL", "FUNDAMENTAL", "QUANT_FACTOR", "NEWS", "RISK",
)
_NEWS_EQUIVALENT_CATEGORIES = ("NEWS", "ANNOUNCEMENT")

# Identifying key per category — "which thing is this item about?" — used to group items that
# make competing claims. Only categories whose `content` schema is actually produced by an
# implemented assembly function in evidence_item.py appear here; inventing a key for a category
# whose content shape is not yet defined anywhere would be guessing at a schema.
_CONFLICT_KEY_FIELDS: Dict[str, Tuple[str, ...]] = {
    "MARKET": ("trading_date",),
    "FUNDAMENTAL": ("report_date",),
    "TECHNICAL": ("indicator", "parameters", "lookback_window"),
}
CONFLICT_DETECTION_SCOPE = (
    "DETERMINISTIC_VALUE_DISAGREEMENT over MARKET/FUNDAMENTAL/TECHNICAL evidence; semantic "
    "contradiction between free-text news items is NOT deterministically detectable and is NOT "
    "claimed to be covered"
)

# Weights for the composite score. Explicit, summed and renormalized at runtime, never hidden
# behind a magic constant. Origin dominates because provenance is the project's primary trust
# axis; recency is the smallest because a stale-but-real fundamental is still a real fundamental.
_WEIGHTS: Dict[str, float] = {
    "origin": 0.35, "coverage": 0.30, "recency": 0.20, "conflict": 0.15,
}
_RECENCY_FRESH_DAYS = 7      # <= this many days old scores 1.0
_RECENCY_STALE_DAYS = 365    # >= this many days old scores 0.0; linear in between
_BAND_HIGH = 0.75
_BAND_MEDIUM = 0.45


@dataclass(frozen=True)
class EvidenceConflict:
    """One unresolved disagreement. Both (or all) sides are named; nothing is resolved here."""
    category: str
    event_date: Optional[str]
    key_repr: str
    evidence_ids: Tuple[str, ...]
    detection: str = "DETERMINISTIC_VALUE_DISAGREEMENT"


@dataclass(frozen=True)
class DataConfidence:
    """The §7 #9 metric. `score` is fully re-derivable from `components` and `_WEIGHTS`."""
    evidence_count: int
    fact_count: int
    model_output_count: int
    origin_breakdown: Dict[str, int]
    real_provider_ratio: float
    present_categories: Tuple[str, ...]
    missing_categories: Tuple[str, ...]
    dated_evidence_count: int
    median_evidence_age_days: Optional[int]
    oldest_evidence_age_days: Optional[int]
    unresolved_conflict_count: int
    conflict_detection_scope: str
    components: Dict[str, float]
    score: float
    band: str
    computed_by: str = "DETERMINISTIC_CODE"  # never an AI self-rating — see module docstring


def _content_key(item: EvidenceItem) -> Optional[str]:
    fields = _CONFLICT_KEY_FIELDS.get(item.category)
    if fields is None or not isinstance(item.content, dict):
        return None
    if not all(f in item.content for f in fields):
        return None
    return compute_canonical_sha256({
        "category": item.category,
        "event_date": item.event_date,
        "key": {f: item.content[f] for f in fields},
    })


def _key_repr(item: EvidenceItem) -> str:
    fields = _CONFLICT_KEY_FIELDS.get(item.category, ())
    parts = [f"{f}={item.content[f]!r}" for f in fields if f in item.content]
    return f"{item.category}({', '.join(parts)})"


def detect_evidence_conflicts(evidence_bundle: List[EvidenceItem]) -> List[EvidenceConflict]:
    """Groups evidence by "the same identified thing at the same date" and flags any group whose
    members carry more than one distinct content. Returns conflicts sorted deterministically, so
    the same bundle always produces the same list in the same order."""
    groups: Dict[str, List[EvidenceItem]] = {}
    for item in evidence_bundle:
        key = _content_key(item)
        if key is None:
            continue
        groups.setdefault(key, []).append(item)

    conflicts: List[EvidenceConflict] = []
    for members in groups.values():
        distinct = {compute_canonical_sha256(m.content) for m in members}
        if len(distinct) < 2:
            continue
        conflicts.append(EvidenceConflict(
            category=members[0].category,
            event_date=members[0].event_date,
            key_repr=_key_repr(members[0]),
            evidence_ids=tuple(sorted(m.evidence_id for m in members)),
        ))
    return sorted(conflicts, key=lambda c: (c.category, c.event_date or "", c.key_repr))


def _present_categories(evidence_bundle: List[EvidenceItem]) -> Tuple[str, ...]:
    seen = {item.category for item in evidence_bundle}
    present = []
    for category in REPORT_EVIDENCE_CATEGORIES:
        if category == "NEWS":
            if any(c in seen for c in _NEWS_EQUIVALENT_CATEGORIES):
                present.append(category)
        elif category in seen:
            present.append(category)
    return tuple(present)


def _evidence_ages_days(evidence_bundle: List[EvidenceItem], as_of: datetime) -> List[int]:
    """Age is measured from `event_date` — the date the underlying fact is about. Items without
    an event_date are simply not counted (their count is reported separately as
    `dated_evidence_count`) rather than being assigned a fabricated age."""
    ages = []
    for item in evidence_bundle:
        if not item.event_date:
            continue
        try:
            event = datetime.strptime(item.event_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        ages.append((as_of.replace(tzinfo=None) - event).days)
    return sorted(ages)


def _median(values: List[int]) -> Optional[int]:
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2 == 1:
        return values[mid]
    return int((values[mid - 1] + values[mid]) / 2)


def _recency_score(median_age: Optional[int]) -> Optional[float]:
    if median_age is None:
        return None
    if median_age <= _RECENCY_FRESH_DAYS:
        return 1.0
    if median_age >= _RECENCY_STALE_DAYS:
        return 0.0
    span = _RECENCY_STALE_DAYS - _RECENCY_FRESH_DAYS
    return round((_RECENCY_STALE_DAYS - median_age) / span, 6)


def compute_data_confidence(
    evidence_bundle: List[EvidenceItem],
    as_of: datetime,
    conflicts: Optional[List[EvidenceConflict]] = None,
) -> DataConfidence:
    """Deterministic: the same bundle and `as_of` always produce the same score.

    Fails closed on an empty bundle — a confidence number computed over nothing would be a
    fabricated reassurance, which is precisely what this metric exists to prevent.
    """
    if not evidence_bundle:
        raise ValueError(
            "FAIL CLOSED: cannot compute Data Confidence over an empty Evidence Bundle."
        )

    conflicts = detect_evidence_conflicts(evidence_bundle) if conflicts is None else conflicts

    origin_breakdown: Dict[str, int] = {}
    for item in evidence_bundle:
        origin_breakdown[item.data_origin] = origin_breakdown.get(item.data_origin, 0) + 1

    total = len(evidence_bundle)
    real_provider_ratio = round(origin_breakdown.get("REAL_PROVIDER", 0) / total, 6)

    present = _present_categories(evidence_bundle)
    missing = tuple(c for c in REPORT_EVIDENCE_CATEGORIES if c not in present)

    ages = _evidence_ages_days(evidence_bundle, as_of)
    median_age = _median(ages)

    components: Dict[str, float] = {
        "origin": real_provider_ratio,
        "coverage": round(len(present) / len(REPORT_EVIDENCE_CATEGORIES), 6),
        "conflict": round(1.0 / (1 + len(conflicts)), 6),
    }
    recency = _recency_score(median_age)
    if recency is not None:
        components["recency"] = recency

    # Weights are renormalized over the components that could actually be measured, so an
    # unmeasurable dimension neither silently scores zero nor silently scores full marks.
    active_weight = sum(_WEIGHTS[name] for name in components)
    score = round(
        sum(components[name] * _WEIGHTS[name] for name in components) / active_weight, 6
    )
    band = "HIGH" if score >= _BAND_HIGH else ("MEDIUM" if score >= _BAND_MEDIUM else "LOW")

    return DataConfidence(
        evidence_count=total,
        fact_count=sum(1 for i in evidence_bundle if i.kind == "FACT"),
        model_output_count=sum(1 for i in evidence_bundle if i.kind == "MODEL_OUTPUT"),
        origin_breakdown=dict(sorted(origin_breakdown.items())),
        real_provider_ratio=real_provider_ratio,
        present_categories=present,
        missing_categories=missing,
        dated_evidence_count=len(ages),
        median_evidence_age_days=median_age,
        oldest_evidence_age_days=ages[-1] if ages else None,
        unresolved_conflict_count=len(conflicts),
        conflict_detection_scope=CONFLICT_DETECTION_SCOPE,
        components=components,
        score=score,
        band=band,
    )
