# 🏛️ AI Quant Research Analyst — Architecture Proposal
## Revision 2 — Reflects Completed Phase-1 Data Infrastructure. AI Is NOT Yet Integrated.

**Status**: Phase 1 (API/data infrastructure) **implemented and committed** (`f75b0ef`); the AI
synthesis layer described in §6-§9 remains **design-only, not built, not wired to any LLM
provider**. This revision updates the document to accurately reflect that split — no new code
changes accompany this revision; it is a documentation-only update. No Phase number assigned,
per standing instruction.
**Baseline**: `main` at `f75b0ef`. Re-confirmed before writing: `git status` shows only this file
as untracked, `434 passed, 11 skipped, 0 failed`.
**Grounding**: every "implemented" claim below was verified by reading the actual committed
source in `f75b0ef`, not assumed — see §1a's status table below.
**AI integration status — stated explicitly per CEO instruction**: **no AI/LLM API has been
called, integrated, or wired into this codebase at any point in this project.** Every "AI"
reference in §6-§9 below describes a *design*, not a running system. The Evidence Layer produces
data; nothing downstream of it currently reads that data except tests.

---

## 1. Goal

A user asks for a research report on one A-share symbol. The system produces a structured,
section-by-section, PIT-correct report that **explains and integrates evidence** — technical,
fundamental, quant-factor, market, news/announcement, and risk — culminating in a **Bull Case**,
a **Bear Case**, and a balanced conclusion. It is explicitly **not** a buy/sell signal generator:
the deliverable is a research document a human analyst reads and judges, not an instruction a
system executes. Every non-trivial claim in the report must be traceable through
`Data → Evidence → Analysis → Conclusion`, and historical reports must never contain information
that would not have been knowable at their `as_of` cutoff.

---

## 1a. Current Implementation Status (as of `f75b0ef`)

| Item | Status | Where |
|---|---|---|
| Canonical Contract — News/Announcement | ✅ **Implemented** | `src/data/contracts/news_announcement.py` — `NewsAnnouncementContract` |
| Canonical Contract — Technical Indicator | ✅ **Implemented** (extends existing `DerivedDataContract`, not a new class — §2.2) | `src/data/contracts/derived.py` |
| Provider abstraction (Adapter) | ✅ **Implemented** — `NewsAnnouncementProvider` ABC + `NewsAnnouncementPage`; `SyntheticNewsAnnouncementProvider` (deterministic fixture) + `LiveNewsAnnouncementProvider` (explicit refusal, no live API wired) | `src/data/providers/base.py`, `src/data/providers/news_provider.py` |
| Persistent News Store (`NewsAnnouncementStore`, mirroring `CorporateActionStore`) | ❌ **Not built** | Items today are validated/PIT-filtered as in-memory lists returned by the Adapter; no stateful, queryable, immutable revision store exists yet for news — a real gap versus this document's original §3.1 draft, corrected here (§3.1) |
| Validation | ✅ **Implemented** — `DataTrustGate.validate_news_announcement()`, `validate_technical_indicator()` | `src/data/validation/gate.py` |
| PIT | ✅ **Implemented** — `PITGate.filter_pit_news_announcements()`, additive, existing `PITGate` methods unmodified | `src/data/validation/pit_gate.py` |
| Evidence Layer | ✅ **Implemented** — `EvidenceItem` + assembly functions for market/fundamental/news/technical evidence, duplicate detection, evidence bundle hashing | `src/quant/evidence/evidence_item.py` |
| Technical Indicators — MA, RSI, MACD | ✅ **Implemented** — real, deterministic, tested calculation | `src/quant/technical/indicators.py` |
| Technical Indicators — Volatility, Momentum, Volume | ❌ **Not implemented** — `NotImplementedError`, design documented in each function's own docstring, honestly disclosed | `src/quant/technical/indicators.py` |
| AI synthesis / LLM Provider integration | ❌ **Not implemented, not started** | N/A — see §6-§9, all still design-only |
| Report Identity, Report persistence, UI | ❌ **Not implemented, not started** | N/A — see §8/§9, all still design-only |

**Everything in this table maps 1:1 onto §2/§3/§4/§5 below** — those sections are updated in
this revision to describe the *implemented* shape precisely (exact field names, exact file
paths), not the earlier draft shape. §6 onward remain unchanged design proposals.

### 1b. Next Phase — explicit pipeline extension

```
[IMPLEMENTED, f75b0ef]                              [NOT YET IMPLEMENTED — next phase]
Evidence Bundle  ──────────────▶  LLM Provider  ──────────────▶  AI Research Analyst  ──────────────▶  Validated Research Report
(EvidenceItem list,                (not yet designed —              (prompts the LLM with              (the post-generation
 hashed, typed FACT/                reserved for the next            ONLY the Evidence Bundle;           validator of §6 runs
 MODEL_OUTPUT, PIT-filtered,        directive; expected to           never raw API data, never           BEFORE anything is
 already committed and              follow this codebase's           live tool/web access during         considered "the report" —
 tested — §5)                       existing Provider-ABC +          generation — §6)                    fail-closed on any
                                     explicit-refusal-until-                                              validator failure — §6)
                                     audited pattern, e.g.
                                     UnifiedDataProvider /
                                     NewsAnnouncementProvider,
                                     but that is a design
                                     decision for that directive,
                                     not this document)
```

This is the literal next-phase scope: an **LLM Provider abstraction** — not designed in this
document, explicitly reserved for the next directive — will sit between the already-built
Evidence Layer and the not-yet-built AI Research Analyst / Report layers. No part of this chain
right of "Evidence Bundle" exists yet.

---

## 2. Architecture

### 2.1 Pipeline

```
Market Data ─────┐
Fundamental Data ─┤
Corporate Actions ┤──▶  PIT Gate (as_of cutoff)  ──▶  Evidence Layer  ──▶  Research Analyst  ──▶  Research Report
Quant Factors ────┤            │                         (deterministic,                (AI: synthesis
News/Announcements┘            │                          code-assembled,                 + citation only)
                                │                          hashed, typed)
                        (existing PITGate +
                         a new, analogous
                         news/announcement
                         gate — §4)
```

Two integration modes, both producing the same report schema:

- **Mode A — Linked to a certified run.** Caller supplies an existing `research_run_id` (already
  produced by `CertifiedResearchRunExecutor.execute()`). Quant Factor Analysis and portfolio
  context are read from that run's stored `result_manifest`/`artifacts` via
  `ResearchRunStore.get_run()` — the exact same read path `research_application.py::
  get_research_run()` already uses. Guarantees the report is consistent with a specific,
  already-certified backtest.
- **Mode B — Single-symbol snapshot (primary use case, matches the directive's own framing
  "针对一只股票").** Caller supplies `symbol` + `as_of`, no backtest required. Quant Factor
  Analysis is computed by calling `FactorRegistry.resolve()`/`FactorRegistry.resolve_all()`
  directly (read-only) for the requested symbol, exactly as `CertifiedResearchRunExecutor`
  already does internally — never a reimplementation of factor scoring logic.

### 2.2 What Already Exists vs. What Is New (verified by reading source, not assumed)

| Component | Status | Notes |
|---|---|---|
| `FactorRegistry` (resolve/resolve_all) | **Reuse as-is** | Only 2 factors registered today (`momentum_20d:v1`, `value_pe:v1`); `RealizedVolatilityFactor` exists but is unregistered — out of this proposal's scope to register it, noted as a pre-existing gap. |
| `MultiFactorEngine`, `SignalEngine` | **Reuse as-is** | Composite scoring / signal bucketing — Quant Factor Analysis section calls these, never re-derives z-scores itself. |
| `PortfolioConstructor` | **Reuse as-is, Mode A only** | Not invoked in Mode B (no portfolio being built for a single-symbol report). |
| `BacktestEngine`/`BacktestResult` | **Reuse as-is, Mode A only** | Never called directly by this feature — only read back from an already-certified run's stored result. |
| `CorporateActionAdjuster`, `CorporateActionStore`, `PITGate` | **Reuse as-is** | Technical Analysis' price series is the SAME PIT-adjusted series the certified pipeline already produces — not a second adjustment implementation. |
| `FinancialMetricsCalculator` | **Reuse as-is** | 4 static methods (PE LYR/TTM, PB, dividend yield). No ROE calculator exists despite the `roe` field on `FundamentalDataContract` — Fundamental Analysis reports ROE as `"NOT_APPLICABLE"` if unset, never computes it ad hoc (Anti-Fabrication principle). |
| `research_application.py::generate_research_report()` | **Reuse as reference, do not duplicate** | Already exists — renders a certification/audit report (provenance, hashes, replay status) for a certified run. The new AI report is a **different document with a different purpose** (symbol-level investment research narrative, not run-provenance audit). Mode A's report **links to** (never re-renders) the existing certification report as an appendix reference. |
| Technical-indicator library (MA, RSI, MACD) | ✅ **Implemented** (`src/quant/technical/indicators.py`) | Deterministic, pure-Python functions consuming the existing PIT-adjusted price series — no new price/adjustment logic, only indicator math over an existing, already-correct series. Volatility/Momentum/Volume indicators remain contract-designed only (`NotImplementedError`), honestly disclosed, not built. |
| News/Announcement contract + provider | ✅ **Contract + Adapter implemented**; ❌ **persistent Store not built** (`src/data/contracts/news_announcement.py`, `src/data/providers/news_provider.py`) | See §3/§4 for the exact implemented shape (differs from this document's original draft — corrected below). |
| Evidence Layer | ✅ **Implemented** (`src/quant/evidence/evidence_item.py`) | The assembly/typing/hashing layer connecting the above to the AI step — see §5. Nothing yet reads its output except tests. |
| AI synthesis + validation harness | ❌ **Not implemented** | See §6 — still design-only. |
| Report Identity + persistence | **New** | See §8. |
| UI | **New Streamlit section**, respecting the existing import boundary (`streamlit_app.py` is the only file permitted to import Streamlit; a new Application Layer module, not the UI file, does all orchestration) — see §9. |

**Explicitly not reimplemented anywhere in this design**: dataset locking, snapshot management,
security master, PIT gating logic for existing data types, corporate-action adjustment, factor
scoring, signal generation, portfolio construction, backtesting, or result hashing. This feature
is a strict consumer of all of the above.

---

## 3. Data

### 3.1 News / Announcement — implemented (`src/data/contracts/news_announcement.py`, `f75b0ef`)

**Corrected from the original draft**: the implemented contract's exact field names/shape differ
from this document's first revision (written before implementation) — reproduced here verbatim
from the committed source, not the earlier draft:

```python
@dataclass(frozen=True)
class NewsAnnouncementContract:
    source_id: str              # provider's own unique id — dedup/lineage anchor
    source: str                  # named source/wire, e.g. "上交所公告" — never "unknown"
    item_type: str                # "NEWS" | "COMPANY_ANNOUNCEMENT" | "REGULATORY_FILING"
    symbols: List[str]           # explicit symbol mentions only — never inferred
    title: str
    body_summary: str            # stored excerpt captured at ingest — never paraphrased later
    source_url: Optional[str]

    published_at: datetime       # when the source published it (event time) — required

    # PIT fields are Optional[datetime] = None (not required, unlike CorporateActionContract) —
    # matching FundamentalDataContract's precedent, so "missing" is representable at the type
    # level, not just via a type-hint-violating None.
    available_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None   # when THIS fetch retrieved it — directive's
                                               # explicit item 4 requirement, not in the
                                               # original draft above

    relevance_score: float = 0.0
    duplicate_cluster_id: Optional[str] = None
    quality_status: str = "VALID"
    data_origin: str = "SYNTHETIC_DATA"
```

`__post_init__` enforces (Contract stage): non-empty `source_id`/`source`/`title`/`symbols`,
`item_type` in the known set. Temporal/business validation (future timestamps, missing PIT
fields) is deliberately kept in `DataTrustGate.validate_news_announcement()` (Validation stage),
not here — see §4.

**`NewsAnnouncementStore` — not built.** The original draft above proposed a store mirroring
`CorporateActionStore`'s stateful, queryable, revision-tracked shape (`add_action`, `query_pit`,
`query_pit_range`). What was actually implemented is narrower: the Adapter
(`SyntheticNewsAnnouncementProvider`) returns validated `NewsAnnouncementContract` lists directly;
`PITGate.filter_pit_news_announcements()` and the Evidence assembly functions operate on those
lists in-memory. There is no persistent, immutable, append-only news revision store yet — a real
gap versus the original design, corrected here rather than left implicit. If a genuine
requirement emerges for revision history on news items (e.g., a corrected headline), that store
would be a separate, focused future item, analogous in size to `CorporateActionStore` itself.

`PITGate.filter_pit_news_announcements()` **is implemented** (§4) — using `published_at`, not
`available_at`, as the primary PIT-visibility timestamp, per the CEO's own literal directive
formula (`published_at <= as_of AND received_at <= as_of`) — a deliberate, disclosed deviation
from this document's original draft (which proposed `available_at`), because for news,
publication *is* the moment of legal citability (unlike a corporate action, where an economic
effective date and its legal disclosure date can genuinely differ). `available_at` remains on the
contract as a descriptive field for the rarer case where legal availability differs from
publication (e.g. an embargo), but is not part of this gate's check.

### 3.2 Duplicate news — ✅ implemented (`detect_duplicate_news()`, `src/quant/evidence/evidence_item.py`)

Two items are one **duplicate cluster** if they share a deterministic key: normalized `title`
(lowercased, alnum/whitespace only) + same `item_type` + sorted `symbols` + `published_at`'s date
— hashed via the same `compute_canonical_sha256` used everywhere else, stored as
`duplicate_cluster_id`, never re-judged by an LLM. All items are preserved in the assembly
function's return value up to that point (nothing is silently dropped before evidence
selection); the Evidence Layer then includes **one representative item per cluster** (earliest
`received_at`, not `available_at` — corrected to match §3.1's `published_at`/`received_at`-based
PIT model) plus a `suppressed_duplicate_count` recorded directly on the representative
`EvidenceItem`'s `content` — implemented and tested (`test_evidence_layer.py`).

### 3.3 Conflicting information

The Evidence Layer does **not** resolve conflicts (e.g., an M&A rumor later denied). Both items
enter the Evidence Layer with their own PIT timestamps. The AI's contract (§6) requires it to
surface an explicit conflict, citing both, rather than silently picking one side — this is a
concrete, testable AI-boundary rule, not a hope.

### 3.4 Historical vs. current-only eligibility

**One rule, not two code paths**: every report is generated *as of* a specific cutoff — `as_of =
today` for a "current" report is simply the same PIT filter (`published_at <= as_of AND
received_at <= as_of`, as actually implemented — §3.1/§4) evaluated at `as_of = now`, not a
separate, PIT-free code path. This
directly satisfies "past reports must never contain future news" without maintaining two parallel
filtering implementations that could drift apart (the exact class of risk the received_at PIT
hardening work closed for corporate actions).

Some evidence categories are **structurally current-only** because they have no well-defined
historical PIT timestamp at all (not because of a runtime judgment call) — e.g. a live order-book
snapshot, or a "current analyst consensus rating" aggregator with no per-rating disclosure date.
These are marked `historical_eligible=False` on the evidence *category* itself; requesting them
for `as_of < today` returns **excluded, with an explicit "NOT AVAILABLE for historical mode"**
marker in the report — never approximated, backfilled, or silently omitted without a trace.

---

## 4. PIT — ✅ implemented (`f75b0ef`, additive only)

- `PITGate.filter_pit_corporate_actions()`, `PITGate.filter_pit_fundamentals()`, and the hardened
  `available_at`/`received_at` dual-cutoff discipline (post the `received_at` hardening,
  `e100cda`) remain **unmodified** — confirmed by `git diff --stat` at implementation time.
- `PITGate.filter_pit_news_announcements(items, as_of_cutoff)` **is implemented**
  (`src/data/validation/pit_gate.py`): `published_at <= as_of AND received_at <= as_of`, either
  timestamp unset (`None`) excludes the item. Uses `published_at`, not `available_at` — see
  §3.1's disclosed rationale for this deliberate deviation from the pre-implementation draft.
- Technical indicators remain **not** given a separate PIT-gate method — implemented and
  documented as a structural property instead: `src/quant/technical/indicators.py`'s functions
  never look beyond their input `dates`/`prices` list bounds, so PIT-safety is inherited from
  whatever series the caller supplies (e.g. `CorporateActionAdjuster`'s already-PIT-correct
  output) rather than re-checked independently. This was an explicit Step 2 architecture
  decision, not an oversight — recorded in the module's own docstring.
- Confirmed via second-pass audit at implementation time: zero changes to
  `CorporateActionAdjuster`, `CorporateActionStore`'s existing methods, `BacktestEngine`, or
  `CertifiedReplayEngine`.

---

## 5. Evidence Layer — ✅ implemented (`src/quant/evidence/evidence_item.py`, `f75b0ef`)

The single architectural hinge between deterministic data and the AI step. `EvidenceItem`, as
actually implemented (field-for-field identical to this document's original draft — no
correction needed here, unlike §3.1):

```python
@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str                 # content-derived, e.g. f"{category}-{sha256(content)[:12]}"
                                      # — a deterministic hash, not a sequential counter
    category: str                    # TECHNICAL | FUNDAMENTAL | QUANT_FACTOR | MARKET |
                                      # NEWS | ANNOUNCEMENT | CORPORATE_ACTION | RISK
                                      # (VALID_EVIDENCE_CATEGORIES, enforced in __post_init__)
    kind: str                        # "FACT" | "MODEL_OUTPUT" — never "AI_INTERPRETATION";
                                      # VALID_EVIDENCE_KINDS, enforced in __post_init__, not
                                      # merely documented
    content: Any                     # a number, short structured record, or short text excerpt
    event_date: Optional[str]        # when the underlying fact/event occurred
    available_at: Optional[datetime]
    received_at: Optional[datetime]
    source: str                      # which system/provider produced this item, by name
    data_origin: str                 # REAL_PROVIDER | LOCAL_PRODUCTION_VERIFICATION_DATA |
                                      # GOLDEN_DATASET | SYNTHETIC_DATA — the SAME 4-tag
                                      # vocabulary used project-wide, not a new one
```

Implemented assembly functions: `assemble_market_evidence()`, `assemble_fundamental_evidence()`
(reuses `PITGate.filter_pit_fundamentals()`), `assemble_news_evidence()` (dedup → Validation →
PIT, in that order, matching the directive's own stated pipeline), `assemble_technical_evidence()`
(excludes `warm_up_satisfied=False` records — their absence from the bundle *is* the signal, not
a hidden gap). `compute_evidence_bundle_hash()` is implemented and tested — canonical
`compute_canonical_sha256` over the full ordered bundle.

- **FACT**: a literal, PIT-visible data point taken verbatim from a certified source (a price, a
  disclosed dividend amount, a news headline, a fundamental ratio's stored value). Never produced
  by the AI.
- **MODEL_OUTPUT**: a deterministic, code-computed quantitative result (factor z-score, composite
  score, technical indicator value, `BacktestResult` field). Computed by existing or new
  deterministic code — never by the LLM.
- The complete, ordered list of `EvidenceItem`s for a report is called the **Evidence Bundle**;
  it is assembled once, in full, before the AI is invoked, and is itself canonically hashed
  (`compute_canonical_sha256`, the same function used everywhere else in this codebase) —
  `evidence_bundle_hash` (§8).

---

## 6. AI Boundary — ❌ NOT IMPLEMENTED (design only; no LLM Provider exists yet — §1b)

**Structural, not just prompted.** The LLM receives the complete, already-assembled Evidence
Bundle as its only input for this task — no live web/tool access during generation, no ability to
introduce a fact that isn't already an `EvidenceItem`.

**Output contract**: every narrative sentence the AI produces that states a fact or draws a
conclusion must carry `evidence_refs: [evidence_id, ...]`. A deterministic **post-generation
validator** (code, not a second LLM call) enforces, before a report is ever considered complete:

1. Every `evidence_refs` entry must resolve to a real `evidence_id` in the bundle — an invented
   or dangling reference fails the report closed.
2. Every number appearing in AI-authored prose must match (within tolerance) a number present in
   at least one of its cited evidence items — a simple, deterministic numeric-hallucination scan,
   not a trust exercise.
3. A sentence with zero `evidence_refs` is only permitted in explicitly-labeled transitional/
   structural prose (e.g. section headers) — never in Bull Case, Bear Case, Risk Analysis, or
   Conclusion content.
4. A detected conflict (§3.3) must appear with both sides cited, or the validator flags it as an
   unaddressed conflict.

**Fail-closed, matching this project's whole convention**: if validation fails, the report is not
published — it returns a `ResearchReportError` with the specific validator failure, exactly the
same fail-closed discipline `CertifiedResearchRunExecutor` already applies everywhere else. There
is no silent fallback to "publish anyway" or "omit the flagged sentence and continue."

**AI's role, defined by exclusion**: the AI never computes a number (all numbers pre-exist as
`MODEL_OUTPUT` evidence before it runs), never fetches data itself, never assigns Data Confidence
(§7, always a computed metric), never silently resolves a conflict, and never produces a single
verdict — Bull Case and Bear Case are both mandatory, by construction (§7), not merely encouraged
by prompt wording.

**Honesty about residual risk**: a deterministic validator catches *structural* hallucination
(invented facts/numbers/citations) but cannot fully verify prose *nuance* (e.g., subtly
overstating a trend's strength while technically citing real numbers) — this is disclosed
explicitly in §10 as a real, not-fully-closed risk, not glossed over.

---

## 7. Report — ❌ NOT IMPLEMENTED (design only)

Ten mandatory sections, each explicitly typed per §5/§6's Fact / Model Output / AI Interpretation
distinction — never a single Buy/Sell verdict:

| # | Section | Primary content type | Fed by |
|---|---|---|---|
| 1 | Executive Summary | AI Interpretation | Generated **last**, after every other section exists, so it summarizes real content rather than being written first and back-filled |
| 2 | Technical Analysis | Model Output | New indicator functions over the existing PIT-adjusted price series (§2.2) |
| 3 | Fundamental Analysis | Fact + Model Output | `FundamentalDataContract` (PIT-filtered) + `FinancialMetricsCalculator`; unset fields (e.g. ROE) reported as `NOT_APPLICABLE`, never estimated |
| 4 | Quant Factor Analysis | Model Output | `FactorRegistry`/`MultiFactorEngine`/`SignalEngine`, unmodified |
| 5 | News / Event Analysis | Fact | PIT-filtered `NewsAnnouncementContract` items, dedup'd, conflicts flagged |
| 6 | Bull Case | AI Interpretation | Cited synthesis of evidence supporting a positive view |
| 7 | Bear Case | AI Interpretation | Cited synthesis of evidence supporting a negative/cautionary view — **mandatory alongside Bull Case, by construction**, directly preventing this from degenerating into a single-verdict signal system |
| 8 | Risk Analysis | Fact + Model Output + AI Interpretation | Volatility/drawdown (Mode A, from `BacktestResult`), data-availability gaps, concentration/liquidity flags, unresolved conflicts (§3.3) |
| 9 | Data Confidence | Model Output only | A **computed** metric — e.g. % `REAL_PROVIDER`-origin evidence, evidence recency, unresolved-conflict count, `historical_eligible` exclusions — never an AI self-rated confidence number |
| 10 | Final Research Conclusion | AI Interpretation | Balanced synthesis + an explicit, prominent "not investment advice" disclaimer, matching `research_application.py`'s existing `LIMITATIONS` convention verbatim |

---

## 8. Identity — ❌ NOT IMPLEMENTED (design only)

Mirrors `ResearchRunIdentity`'s established pattern, extended with the fields this feature
specifically needs (per the directive's own checklist — all seven are recommended, none omitted):

```python
@dataclass(frozen=True)
class ResearchAnalystReportIdentity:
    report_id: str                  # e.g. f"report_{symbol}_{as_of}_{uuid4().hex[:12]}"
    symbol: str
    as_of: str                      # the PIT cutoff the ENTIRE report is anchored to
    research_run_id: Optional[str]  # set in Mode A, None in Mode B — never fabricated
    evidence_bundle_hash: str       # compute_canonical_sha256 over the full Evidence Bundle
    data_snapshot_id: Optional[str] # links to SnapshotManager where market/fundamental data
                                     # participates, reusing the existing snapshot concept
    model_version: str              # e.g. "claude-sonnet-5" — which model generated the prose
    prompt_version: str             # versioned prompt/analyst-logic identifier, trailing-
                                     # versioned like schema_version/adjustment_algorithm_version
                                     # — a future prompt change never silently redefines an old
                                     # report's meaning
    code_version: str               # get_code_version() — reused verbatim, not reimplemented
    code_state: str
    generated_at: str               # wall-clock generation time — distinct from `as_of`
```

**Honest reproducibility scope — the most important design decision in this section**: unlike
`ResearchRunIdentity.result_hash`, this feature does **not** claim the AI's prose is
bit-reproducible — an LLM is not guaranteed deterministic even given an identical input. What
*is* reproducible, exactly like the rest of this codebase's certification guarantees:

- `evidence_bundle_hash` proves the Evidence Bundle itself has not been tampered with post-hoc.
- Every `MODEL_OUTPUT` evidence item is independently re-derivable from source (same as Replay
  re-derives factor/portfolio values) — a `verify_evidence_bundle_integrity()` function, mirroring
  `verify_result_manifest_integrity()`'s existing pattern, would re-run the deterministic
  computations and compare.
- Every `FACT` evidence item is a stored, immutable, point-in-time capture — verifiable against
  its own stored hash, not "recomputable" (news isn't recomputed, it's captured once).
- The AI-authored prose is **not** re-verified byte-for-byte; regenerating a report from the same
  `evidence_bundle_hash` may legitimately produce different wording. This is disclosed to the
  reader in the UI (§9), not hidden — a false "this report is fully reproducible" claim would
  contradict this project's own established honesty standard (the same standard that led to
  Phase 9 correcting an inaccurate precision claim, and to disclosing the PIT `received_at` gap
  rather than glossing over it).

---

## 9. UI — ❌ NOT IMPLEMENTED (design only)

New section in the existing Streamlit app, respecting the established import boundary exactly:
`streamlit_app.py` remains the only file permitted to import Streamlit; all orchestration lives
in a new Application Layer module (e.g. `research_analyst_application.py`, mirroring
`research_application.py`'s own "zero business logic in the UI file" convention) that
`streamlit_app.py` calls into, never the reverse.

Proposed layout:

- **Selector row**: symbol (from the existing certified universe) + `as_of` date (bounded by
  `get_available_as_of_range()`, reused as-is) + optional linked `research_run_id` (Mode A).
- **Section-by-section rendering** of the 10 report sections (§7), each claim visually tagged
  with a small badge — `FACT` / `MODEL OUTPUT` / `AI INTERPRETATION` — so provenance is visible
  at a glance, not just tracked internally.
- **Click-to-expand citations**: every cited `evidence_id` expands inline to show its full
  content, timestamps, and `data_origin` — no claim is un-auditable from the UI itself.
- **Data Confidence badge**: the computed metric (§7 #9) rendered prominently, near the top.
- **Conflict banner**: any unresolved conflicting-evidence flag (§3.3) surfaced explicitly, not
  buried in prose.
- **Prominent disclaimer banner**: "not investment advice," matching the app's existing
  disclaimer conventions verbatim.
- **"View Evidence Bundle" raw expander**: the full, hashed Evidence Bundle as JSON — full
  transparency, matching this project's consistent preference for surfacing hashes/provenance
  rather than hiding them behind a polished summary.
- **Reproducibility note**: explicit, visible text distinguishing "evidence is hash-verified" from
  "AI prose is not guaranteed byte-identical on regeneration" (§8) — never implied to be more
  reproducible than it is.

---

## 10. Risks

1. **News/announcement infrastructure is entirely new** — the largest build item, with no
   existing provider integration (like `TUSHARE_TOKEN`/live-provider gating elsewhere, a real
   news feed is a separate, later concern; only `GOLDEN_DATASET`/`SYNTHETIC_DATA` fixtures would
   exist initially, mirroring `golden_dataset_seed.py`'s existing pattern).
2. **Residual hallucination risk is real, not fully closed** — the validator (§6) catches
   structural fabrication (invented facts, numbers, citations) but not all forms of subtle
   misrepresentation within an otherwise-cited sentence. Disclosed, not hidden.
3. **LLM cost/latency and non-determinism** — every report generation is an LLM call; identical
   inputs are not guaranteed identical prose output (§8's honest reproducibility framing exists
   specifically because of this).
4. **Evidence Bundle size** — a long history of news/fundamentals for one symbol could exceed
   practical prompt-size budgets; needs an explicit, disclosed evidence-selection/summarization
   policy (out of scope to design in this proposal) rather than silent truncation.
5. **Data Confidence metric could be gamed or misleading if under-specified** — needs a concrete,
   reviewed formula before implementation, not left as "some confidence score."
6. **Model/prompt version drift** — `model_version`/`prompt_version` (§8) exist specifically so a
   future model or prompt change never retroactively redefines what an already-generated report
   meant, mirroring `schema_version`/`adjustment_algorithm_version` precedent — but this requires
   implementers to actually bump these versions on every real change, a process risk, not just a
   schema one.
7. **Scope size** — this is the largest single feature proposed this session; §11 recommends
   phasing specifically to keep any one authorized implementation directive reviewable.

---

## 11. Implementation Plan — updated to reflect completed steps

1. ✅ **DONE** (`f75b0ef`) — News/Announcement contract, provider adapter, and
   `filter_pit_news_announcements()` (extends the existing PIT pattern to a new data type).
   Persistent `NewsAnnouncementStore` remains **not built** (§3.1) — a narrower delivery than
   originally planned, disclosed rather than silently dropped.
2. ✅ **DONE** (`f75b0ef`) — Technical-indicator function library: MA/RSI/MACD implemented and
   tested; Volatility/Momentum/Volume remain contract-only (`NotImplementedError`).
3. ✅ **DONE** (`f75b0ef`) — Evidence Layer assembly (`EvidenceItem` + market/fundamental/news/
   technical assembly functions, duplicate detection, bundle hashing).
4. ❌ **NEXT — not authorized by this document; reserved for the next directive.** An LLM
   Provider abstraction (§1b) + AI synthesis + the deterministic validation harness (§6) — the
   harness should be built and tested *before* wiring in a live LLM call, so validation logic is
   proven against hand-crafted adversarial evidence bundles first. This is the literal
   `Evidence Bundle → LLM Provider → AI Research Analyst → Validated Research Report` chain
   from §1b.
5. ❌ Not started — `ResearchAnalystReportIdentity` + persistence (mirrors `ResearchRunStore`'s
   existing pattern).
6. ❌ Not started — Streamlit UI section, via a new Application Layer module.

Each remaining step is independently reviewable and independently authorizable — this proposal
continues to recommend treating them as separate future directives, not one large
implementation, consistent with how every prior phase this session was scoped and approved
incrementally, and consistent with steps 1-3 above having in fact been delivered as their own
focused directive rather than all six at once.

---

## Final Report

**AI QUANT RESEARCH ANALYST — ARCHITECTURE PROPOSAL — REVISION 2**

**Status**: Phase 1 data infrastructure **implemented and committed** (`f75b0ef`,
`434 passed, 11 skipped, 0 failed`). AI synthesis (§6-§9) remains **design-only — no LLM API has
been called or integrated anywhere in this codebase.** This revision is a documentation-only
update; no code changed to produce it.

**Implemented** (§1a/§2.2, verified against committed source): Canonical Contract
(`NewsAnnouncementContract`, extended `DerivedDataContract` for indicators), Provider abstraction
(`NewsAnnouncementProvider` ABC, `SyntheticNewsAnnouncementProvider`, explicit-refusal
`LiveNewsAnnouncementProvider`), Validation (`DataTrustGate` extended), PIT
(`PITGate.filter_pit_news_announcements()`, additive), Evidence Layer (`EvidenceItem` + assembly
functions, duplicate detection, bundle hashing), Technical Indicators MA/RSI/MACD (real,
deterministic, tested — a warm-up off-by-one bug was caught and fixed during testing).

**Not implemented, honestly disclosed**: persistent `NewsAnnouncementStore` (news items are
validated/PIT-filtered in-memory, not held in a stateful revision store — §3.1); Volatility/
Momentum/Volume technical indicators (`NotImplementedError`, contract-documented only); and
everything in §6-§9 (AI boundary, Report, Identity, UI) — none of it built, none of it wired to
any LLM provider.

**Next phase, explicit** (§1b): `Evidence Bundle → LLM Provider → AI Research Analyst →
Validated Research Report`. The Evidence Bundle side is done and tested. The LLM Provider
abstraction is **not designed in this document** — reserved for the next directive, expected to
follow this codebase's established Provider-ABC + explicit-refusal-until-audited pattern, but
that is a decision for that directive, not this one.

**Corrections made in this revision** (§3.1/§3.2/§4): the actual `NewsAnnouncementContract`
field names differ from the original pre-implementation draft (`source_id`/`title` not
`item_id`/`headline`; added `retrieved_at`); PIT visibility uses `published_at`, not
`available_at`, per the CEO's own literal directive formula; no persistent news store was built.
All corrected to match the committed source exactly, not left as stale draft text.

**Report/AI Boundary/Identity/UI design** (§6-§9): unchanged from Revision 1, still valid as
*design* for the next phase — 10 mandatory sections with both Bull and Bear Case mandatory by
construction (never a single verdict), a structural (not merely prompted) post-generation
validator, an honest reproducibility scope (Evidence Bundle is hash-verifiable; AI prose is not
claimed to be bit-reproducible).

**Risks**: unchanged from §10, still applicable to the next phase.

**Production Impact (this revision)**:
```
Production Code Modified: NO (this is a documentation-only revision)
Tests Modified: NO
Dependencies Modified: NO
Commit Created: pending this commit (proposal document only)
Push Performed: NO
```
Prior infrastructure commit `f75b0ef` (already merged, separately authorized and reported) is
unaffected by this revision.

**Recommendation**: **PHASE 1 COMPLETE. READY FOR NEXT-PHASE DIRECTIVE** (LLM Provider design/
implementation) **— not authorized by this document.**
