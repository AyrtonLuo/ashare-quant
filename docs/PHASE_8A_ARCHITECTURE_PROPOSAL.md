# Phase 8A Architecture Proposal
**Factor Engine & Research Signal Certification — Design Only, No Implementation**

**Directive ID**: CEO-2026-08-03-RESEARCH-008A-STEP2
**Status**: PROPOSAL — awaiting CEO review. No production code, tests, or data were modified to produce this document.
**Baseline**: Phase 7J frozen at commit `f951a91`, 228 passed / 11 skipped / 0 failed, `TUSHARE_TOKEN` unavailable.

---

## 1. Executive Summary

The Phase 8A read-only audit (Step 1) found that almost every component a Factor Engine needs already exists in this codebase — `BaseFactor` and four concrete factors (`PriceMomentumFactor`, `RealizedVolatilityFactor`, `ValuationFactorAdapter`, `AverageVolumeFactor`), `FactorNormalizer`, `MultiFactorEngine`, `SignalEngine`, `SimpleMomentumStrategy`, `PortfolioConstructor` — each independently unit-tested. None of them is called from `CertifiedResearchRunExecutor`, which currently builds portfolio weights as hard-coded equal-weight across the whole universe. This is the exact "component exists, bound into a hash, never actually executed" bug class Phase 7I found for corporate actions and Phase 7J found (in its own first draft) for the cost model.

This proposal is therefore primarily an **integration and identity-binding design**, not a from-scratch build. It defines: a `FactorRegistry` that makes `factor_id` strings resolve to exactly one executable implementation (closing the "identity says X, execution does Y" gap); a fundamental-data input channel for the Value factor, structurally parallel to the existing `raw_price_series`; explicit rules for cross-sectional normalization determinism under replay; one new identity hash (`signal_configuration_hash`) added as a backward-compatible defaulted field; and an extension of `CertifiedReplayEngine` that recomputes factors → signals → portfolio weights from source data, not from cached artifacts, mirroring exactly the pattern Phase 7J already established for corporate-action and cost-model replay verification.

---

## 2. Current Architecture

Two threads, currently disconnected:

**Certified research path (Phase 7J):**
```
CertifiedResearchRequest
  → PersistentDatasetLock, DatasetVersionLock, SecurityMasterRegistry, provenance checks
  → CorporateActionAdjuster.adjust() [mandatory]
  → hard-coded equal-weight PortfolioTarget   ← THE GAP
  → BacktestEngine(cost_model=TransactionCostModel(**cost_model_config))
  → ResearchRunIdentity / ResearchInputManifest (factors_config bound as opaque, unexecuted metadata)
  → ResearchRunStore.create_run()
```

**Factor/signal/strategy components (exist, untested end-to-end, never called by the above):**
```
BaseFactor (momentum.py, volatility.py, value.py, liquidity.py)
  → FactorNormalizer.normalize_cross_section()
  → MultiFactorEngine.compute_composite_scores()  [or SignalEngine directly for a single factor]
  → SignalEngine.generate_signals()
  → SimpleMomentumStrategy.generate_target_portfolio()
  → PortfolioConstructor.build_portfolio()
```

## 3. Identified Gap

1. No orchestration code connects the two threads.
2. No `FactorRegistry`: `factors_config` (e.g. `[{"factor": "momentum_20d:v1"}]`) is validated only for non-emptiness; nothing parses it into an executable `BaseFactor` instance.
3. `CertifiedResearchRequest` has no fundamental-data input field, so `ValuationFactorAdapter` cannot be fed.
4. `CertifiedReplayEngine` re-verifies dataset bytes, snapshot, corporate-action data, and cost model — but since no factor/signal/portfolio step exists yet, it has nothing to re-verify there.
5. Two portfolio-construction implementations exist (`SimpleMomentumStrategy.generate_target_portfolio`, `PortfolioConstructor.build_portfolio`) with complementary, non-overlapping responsibilities that have never been chained together.

---

## 4. Target Architecture

```
CertifiedResearchRequest
  (adds: factor_definitions: List[FactorSpec], fundamental_data: Dict[str, List[FundamentalDataContract]],
         signal_config: List[FactorWeightConfig])
        │
        ▼
Control 1-5 (unchanged): PersistentDatasetLock, DatasetVersionLock, as_of/PIT, SecurityMasterRegistry,
                          provider_data_origin  — all exactly as Phase 7J built them
        │
        ▼
Control 6 (unchanged): CorporateActionAdjuster.adjust() — mandatory, per symbol → ADJUSTED price series
        │
        ▼
[NEW] Control 7: FactorRegistry.resolve(factor_id, parameters) for every entry in factor_definitions
        → FAIL CLOSED on unknown factor_id
        │
        ▼
[NEW] Control 8: Per-symbol factor calculation (PIT-filtered)
        Momentum ← adjusted price series (from Control 6)
        Value    ← fundamental_data, PIT-filtered by available_at/received_at, MetricProvenance-checked
        → FactorValue per (factor, symbol); FAIL CLOSED if a factor's required data source is entirely absent
        │
        ▼
[NEW] Control 9: FactorNormalizer.normalize_cross_section() per factor, over the LOCKED universe
        → FAIL CLOSED if fewer than MIN_CROSS_SECTIONAL_SAMPLE (proposed: 3) valid values
        │
        ▼
[NEW] Control 10: MultiFactorEngine.compute_composite_scores(signal_config) → composite score per symbol
        │
        ▼
[NEW] Control 11: SignalEngine.generate_signals() → List[SignalRecommendation]
        │
        ▼
[NEW] Control 12: GenericFactorStrategy.generate_target_portfolio(signals, top_n)
        → raw weights (replaces the hard-coded equal-weight block)
        │
        ▼
[NEW] Control 13: PortfolioConstructor.build_portfolio(raw_weights, ...) → PortfolioTarget
        │
        ▼
Control 14 (unchanged): TransactionCostModel(**cost_model_config) → BacktestEngine.run_backtest()
        │
        ▼
Identity: factor_definition_hash (real, resolved config) + signal_configuration_hash [NEW]
          + parameter_hash + transaction_cost_model_hash + universe_hash + dataset_manifest_hash
          + code_version/code_state  →  ResearchRunIdentity
        │
        ▼
ResearchRunStore.create_run()  (unchanged, still fails closed on collision)
```

Replay mirrors this exactly (§17), recomputing Controls 6–14 from stored raw inputs rather than trusting any cached derived artifact.

---

## 5. Data Flow — Step-by-Step Contract

| Step | Input | Output | Owner | Verifier | Failure condition |
|---|---|---|---|---|---|
| Dataset/snapshot/universe/provenance | `CertifiedResearchRequest` | `LockedDatasetState`, `LockedPersistentDatasetState` | `PersistentDatasetLock`, `DatasetVersionLock`, `SecurityMasterRegistry` (unchanged from 7J) | Gate | Unchanged from Phase 7J |
| Corporate-action adjustment | raw price series + `CorporateActionStore` | adjusted price series | `CorporateActionAdjuster` (unchanged) | Gate | Unchanged from Phase 7I/7J |
| Factor resolution | `factor_definitions: List[FactorSpec]` | resolved `BaseFactor` instances + `FactorDefinition` records | **`FactorRegistry`** (new) | Gate | Unknown `factor_id` → FAIL CLOSED |
| Factor calculation | adjusted prices (momentum) / PIT-filtered fundamentals (value) | `FactorValue` per (factor, symbol) | `BaseFactor.compute()` (existing, momentum/value) | Gate (checks `FactorStatus`) | Required data source entirely absent for a factor across the whole universe → FAIL CLOSED. Per-symbol absence → `FactorStatus.MISSING`/`NOT_APPLICABLE`, that symbol excluded from that factor only. |
| Normalization | `List[FactorValue]` for one factor, one date, locked universe | `Dict[symbol, z_score]` | `FactorNormalizer` (existing) | Gate | Fewer than 3 valid values → FAIL CLOSED (`INSUFFICIENT_CROSS_SECTIONAL_SAMPLE`, new rule — see §12) |
| Composite scoring | `Dict[factor_name, Dict[symbol, z_score]]` + `signal_config` | `Dict[symbol, composite_score]` | `MultiFactorEngine` (existing) | Gate | N/A — pure aggregation of already-validated inputs |
| Signal generation | composite scores | `List[SignalRecommendation]` | `SignalEngine` (existing) | Gate | N/A |
| Raw weights | signals, `top_n` | `Dict[symbol, weight]` | **`GenericFactorStrategy`** (new, see §14) | Gate | Zero BUY-biased candidates → empty portfolio is a valid (not failed) result, matching existing `SimpleMomentumStrategy` semantics |
| Weight validation | raw weights | `PortfolioTarget` | `PortfolioConstructor` (existing) | Gate | N/A — clips/renormalizes, does not fail closed today (unchanged) |
| Backtest | `PortfolioTarget`, adjusted prices, `TransactionCostModel` | `BacktestResult` | `BacktestEngine` (unchanged) | Gate | N/A |
| Identity | every hash above | `ResearchRunIdentity` | Gate | `ResearchRunStore.create_run` | Duplicate `research_run_id` → FAIL CLOSED (unchanged) |

---

## 6. FactorRegistry Design

```python
@dataclass(frozen=True)
class FactorSpec:
    factor_id: str                    # "momentum_20d:v1" — name AND version in one string
    parameters: Dict[str, Any]        # e.g. {"window_days": 20} or {"metric": "pe_ttm"}

@dataclass(frozen=True)
class FactorDefinition:
    factor_id: str
    factor_class: str                 # fully-qualified class name, for audit trail
    data_source: str                  # "MARKET_DATA" | "FUNDAMENTAL_DATA"
    direction: FactorDirection        # POSITIVE | NEGATIVE (reuse multi_factor.py's existing enum)
    parameters: Dict[str, Any]

class FactorRegistry:
    _entries: Dict[str, Tuple[Callable[[Dict[str, Any]], BaseFactor], str, FactorDirection]] = {}

    @classmethod
    def register(cls, factor_id, factory, data_source, direction): ...
    @classmethod
    def resolve(cls, spec: FactorSpec) -> Tuple[BaseFactor, FactorDefinition]: ...
```

- **Registration mechanism**: explicit calls at module import time (e.g. `FactorRegistry.register("momentum_20d:v1", lambda p: PriceMomentumFactor(**p), "MARKET_DATA", FactorDirection.POSITIVE)`), collected in a single `src/quant/factors/registry.py`. Not a decorator-scanning/plugin-discovery mechanism — explicit and auditable, consistent with this codebase's preference for explicit fail-closed code over "magic."
- **Duplicate `factor_id`**: `register()` raises `ValueError: FAIL CLOSED` if the id is already registered — mirrors `ResearchRunStore`/`PersistentDatasetManifestStore`'s existing immutability pattern.
- **Unknown `factor_id` at resolve time**: `resolve()` raises `ValueError: FAIL CLOSED: unknown factor_id`. This is the mechanism that makes `factor_definition_hash` trustworthy — since the gate can never proceed past resolution without a match, the hash of `factor_definitions` and the set of factors actually executed are the same object by construction, not by convention.
- **Versioning**: version is part of the `factor_id` string (existing project convention, already used as `"momentum_20d:v1"` throughout Phase 7 tests). A semantic change to a factor's calculation logic must ship as a new `factor_id` (e.g. `v2`), never a silent behavior change under an existing id — proposed as an explicit project convention, not previously written down.
- **Parameter canonicalization**: `compute_canonical_sha256(factor_definitions)` where `factor_definitions: List[FactorSpec]`-as-dicts, using the existing unified `canonical.py` (no new serializer). List order is caller-significant (per `canonical.py`'s documented "list order preserved" rule) — the gate will sort `factor_definitions` by `factor_id` before hashing, so callers cannot produce two different hashes for the logically-identical configuration by reordering the list.
- **Registry change vs. `code_version`**: any change to a registered factor's implementation changes the git commit, hence `code_version` (already bound in identity since Phase 7A/7J). `factor_id` + `code_version` together fully pin down behavior; `factor_id` alone across different commits is not a completeness guarantee — this is consistent with how every other component in this system is version-pinned (the corporate-action adjuster, cost model, etc. carry no independent version field either — they rely on `code_version`).

---

## 7. FactorDefinition Design

Already specified above (§6). One clarification: `required_fields` (mentioned in the directive) is not stored as a separate declarative list — it is implicit in `data_source` (`MARKET_DATA` factors require the adjusted price series; `FUNDAMENTAL_DATA` factors require `fundamental_data[symbol]`) plus whatever `BaseFactor.compute()`/`compute_from_fundamental()` itself checks (e.g. `ValuationFactorAdapter` already checks `MetricProvenance`). Declaring a parallel `required_fields` list that must be kept in sync by hand would be exactly the kind of unenforced duplicate-source-of-truth this whole phase is trying to eliminate — the registry's `data_source` tag plus the factor class's own validation is the single source of truth.

---

## 8. Momentum Factor

- **Class**: `PriceMomentumFactor` (existing, `src/quant/factors/momentum.py`, unmodified).
- **Input**: the `CorporateActionAdjuster`-adjusted price series already produced by the gate's existing mandatory Control 6 — **not** `raw_price_series` directly. This is important: computing momentum on raw (unadjusted) prices would reproduce the exact false-signal bug Phase 7I fixed for backtest returns (a stock split would look like a momentum crash).
- **PIT**: `as_of` passed straight through from the request; the factor itself only ever sees price history up to (and including) dates already constrained by the gate's existing PIT machinery upstream.

## 9. Value Factor

- **Class**: `ValuationFactorAdapter` (existing, `src/quant/factors/value.py`, unmodified). Metric selectable via `parameters: {"metric": "pe_ttm"}` (or `"pb"`).
- **Input**: the PIT-selected `FundamentalDataContract` per symbol (see §10).
- **PIT**: enforced twice — once by the gate's fundamental-data PIT filter (§10) selecting which record is visible at `as_of`, and again by `ValuationFactorAdapter.compute_from_fundamental`'s existing `MetricProvenance` check (`CURRENT_ONLY`/`NOT_PIT_VERIFIED`/`UNAVAILABLE` → `FactorStatus.NOT_APPLICABLE`, never a valid historical value). No change needed to this class — its PIT logic was already correct, just never invoked in production.
- **If required data missing project-wide**: `FACTOR_NOT_SUPPORTED_BY_CURRENT_DATA_SCHEMA` is not a new enum value on `FactorStatus` — it is a **gate-level FAIL CLOSED** raised before calculation even starts, if `fundamental_data` is entirely absent from the request while a `FUNDAMENTAL_DATA`-sourced factor is requested. Per-symbol absence remains `FactorStatus.NOT_APPLICABLE` (existing enum, unchanged), which is not a run-level failure.

## 10. Fundamental Data Input

New field on `CertifiedResearchRequest`:

```python
fundamental_data: Dict[str, List[FundamentalDataContract]]   # symbol -> ALL known revisions, unfiltered
```

- **Symbol mapping**: dict key = symbol, identical convention to `raw_price_series`.
- **Date mapping**: each `FundamentalDataContract` self-describes via `report_date` (the period it covers) and `trade_date`; no separate date parameter needed.
- **`available_at`/`received_at`**: already fields on `FundamentalDataContract` (unlike `CorporateActionContract` before Phase 7I, this contract already has them). The gate applies a new `PITGate.filter_pit_fundamentals(records, as_of)` (structurally identical to Phase 7I's `filter_pit_corporate_actions`, proposed as a new one-line static method).
- **Revision handling**: multiple records per symbol (e.g. a restated annual report) are handled exactly like `CorporateActionStore`'s "latest visible" selection: among PIT-visible records for a symbol, take the one with the latest `report_date`; break ties by latest `available_at`. This requires no new store class — a plain filter+sort over the caller-supplied list, since Phase 8A is explicitly not building a persisted fundamental warehouse.
- **`as_of` filtering**: `available_at <= as_of AND received_at <= as_of`, identical rule to every other PIT gate in this codebase.
- **Missing data**: symbol absent from `fundamental_data` entirely, or present but zero PIT-visible records → `FactorStatus.NOT_APPLICABLE` for that symbol only (existing enum). `fillna(0)` or any current-value substitution remains explicitly prohibited, consistent with Phase 7 principles.
- **Value factor reads**: orchestration layer extracts `getattr(selected_record, parameters["metric"])` (e.g. `.pe_ttm`) and `selected_record.provenance`, then calls the existing `ValuationFactorAdapter.compute_from_fundamental(...)`.
- **Future extension to a persisted `FundamentalDataWarehouse`**: structurally trivial — `HistoricalDataWarehouse`/`ParquetStorageAdapter` already exist for market data; a parallel adapter storing `FundamentalDataContract` rows under `data/research/<dataset_id>/fundamentals/` would produce the same `List[FundamentalDataContract]` shape this proposal already consumes. No interface change would be needed in the factor/gate layer, only in how `fundamental_data` gets populated before being passed into the request — this is deliberately designed so that swap is possible later without touching `FactorRegistry`, `BaseFactor`, or the gate's Control 8.

---

## 11. PIT Enforcement (Summary — see §9/§10 for factor-specific detail)

| Data | PIT rule | Enforced by |
|---|---|---|
| Market data (momentum input) | Upstream, before reaching the gate (Phase 7J's existing disclosed limitation — unchanged) | `HistoricalDataWarehouse`/`PITGate.filter_pit_contracts` (caller's responsibility) |
| Corporate actions | `available_at <= as_of` | `PITGate.filter_pit_corporate_actions` (Phase 7I, unchanged) |
| Fundamental data (value input) | `available_at <= as_of AND received_at <= as_of` | **`PITGate.filter_pit_fundamentals`** (new, structurally identical to the corporate-action filter) |
| Fundamental provenance | `CURRENT_ONLY`/`NOT_PIT_VERIFIED`/`UNAVAILABLE` rejected | `ValuationFactorAdapter.compute_from_fundamental` (existing, unchanged) |
| Snapshot/dataset `as_of` | `as_of == locked_snapshot.as_of` | Gate Control (Phase 7J, unchanged) |

No `datetime.now()` is introduced anywhere in this design as a stand-in for historical `as_of` — every new code path threads the caller-supplied `as_of` through explicitly, matching the pattern audited clean in Phase 7J.

---

## 12. Cross-sectional Normalization — Determinism Design

This is the highest-risk area per the directive, addressed explicitly:

- **Per-symbol vs. per-date+universe**: `BaseFactor.compute()` is called once per symbol (independent, no cross-symbol dependency). `FactorNormalizer.normalize_cross_section()` is called once per factor **per rebalance date**, over the full **locked** universe's `FactorValue` list for that date — never a caller-supplied "current" universe.
- **Universe determinism**: the gate threads `sorted(request.universe_symbols)` (already validated by `SecurityMasterRegistry.is_tradable_on` in the existing Control 4) into factor calculation and normalization. Because this list is already part of `universe_hash` in the identity, replay reconstructing the same `universe_hash` reconstructs the same normalization input set by construction.
- **Missing factor per symbol**: excluded from that factor's cross-sectional statistics — already `FactorNormalizer`'s existing behavior (filters to `FactorStatus.VALID` before computing mean/std). No change needed.
- **Insufficient sample — NEW rule**: `FactorNormalizer` today silently returns all-zero z-scores when `std == 0` (e.g., only one valid value, or all values identical). This proposal adds a gate-level check **before** calling the normalizer: **fewer than 3 valid `FactorValue`s for a factor on a given date → FAIL CLOSED** (`ValueError: FAIL CLOSED: insufficient cross-sectional sample for factor '{factor_id}' (N valid, minimum 3)`), rather than silently emitting a degenerate all-zero signal that could masquerade as "no preference" when it is actually "too little data to compute a preference." This is new project-wide policy proposed here for CEO approval — it does not exist in current code and is stricter than `FactorNormalizer`'s current default behavior (which is left unmodified for its own unit tests; the new check lives in the gate, one layer up).
- **Winsorization / mean / std**: unchanged, existing 3-sigma clip + z-score in `FactorNormalizer`.
- **Deterministic ordering**: `FactorValue` list constructed in `sorted(universe_symbols)` order before being passed to the normalizer, for audit-trail and byte-reproducibility purposes (the normalizer's numeric output is order-independent since it returns a dict, but a canonical construction order removes any ambiguity when this list is itself serialized as an audit artifact).
- **Replay determinism**: replay reconstructs `universe_symbols` from the stored `ResearchRunIdentity.universe_definition` (never re-queries "current" `SecurityMasterRegistry` state), same `as_of`, same `factor_definitions` (resolved via the same immutable `FactorRegistry`), and recomputes from stored raw price/fundamental artifacts. Residual floating-point noise across runs is absorbed by `canonical.py`'s existing 6-decimal rounding at the point the final result is hashed — the same safety margin already relied upon for every other hash in this system since Phase 7A.

---

## 13. Signal Architecture

Responsibility chain, each box existing and reused verbatim except where marked **[NEW]**:

| Component | Responsibility | Reused as-is? |
|---|---|---|
| `BaseFactor` implementations | data → `FactorValue` | Yes |
| `FactorNormalizer` | `List[FactorValue]` → cross-sectional z-scores | Yes (+ new gate-level minimum-sample check, §12) |
| `MultiFactorEngine` | multiple factors' z-scores → composite score | Yes |
| `SignalEngine` | composite score → `SignalRecommendation` | Yes |
| **`GenericFactorStrategy`** | signals → raw weights | **[NEW]**, see §14 |
| `PortfolioConstructor` | raw weights → validated `PortfolioTarget` | Yes |

---

## 14. Portfolio Construction — `SimpleMomentumStrategy` vs. `GenericFactorStrategy`

**Recommendation: add a new `GenericFactorStrategy` class; do not rename or modify `SimpleMomentumStrategy`.**

Reasoning: `SimpleMomentumStrategy.generate_target_portfolio()`'s actual logic (rank `SignalRecommendation`s by `signal_score`, take top N, equal-weight) does not reference momentum anywhere — it already operates purely on the generic `SignalRecommendation` type. Functionally it is already factor-agnostic. The problem is naming and honesty of the audit trail: this Phase 8A design combines Momentum **and** Value into one composite signal, and certifying that run under a class literally named `SimpleMomentumStrategy` would misrepresent what actually drove the portfolio, which conflicts with this project's anti-fabrication principles about honest labeling. The minimal-diff fix is a new class with identical logic and an honest name, not a rename (which would touch `SimpleMomentumStrategy`'s own existing, currently-passing `test_momentum_strategy.py`) and not a deeper rewrite (the logic itself needs zero changes). `GenericFactorStrategy` would either subclass or literally duplicate the ~10 lines of `generate_target_portfolio`; final choice (subclass vs. duplicate) is an implementation-time decision, not an architectural one — both preserve `SimpleMomentumStrategy` and its test untouched.

`PortfolioConstructor.build_portfolio` is reused unmodified downstream of whichever strategy produces raw weights — its tradability-filtering and renormalization responsibilities are unaffected by which strategy produced the input.

---

## 15. Identity Binding

| Bound content | Field | Status |
|---|---|---|
| Every factor's `factor_id` + parameters, executed via `FactorRegistry` | `factor_definition_hash` | Existing field, now bound to what's *actually resolved and executed*, not an opaque caller string |
| Composite weighting: which factors combine, at what weight, what direction (`List[FactorWeightConfig]`) | **`signal_configuration_hash`** | **NEW field** |
| `strategy_id`/`strategy_version`, `top_n`, any other portfolio-construction-level knob | `parameter_hash` | Existing field, reused — this is already `strategy_parameters`' documented purpose |
| Cost model | `transaction_cost_model_hash` | Existing, unchanged |
| Universe | `universe_hash` | Existing, unchanged |
| Dataset | `dataset_manifest_hash` | Existing, unchanged |
| Snapshot/as_of | `snapshot_id`, `as_of` | Existing, unchanged |
| Code | `code_version`, `code_state` | Existing, unchanged |

**Why only one new hash, not two or three**: the directive suggests "signal configuration hash and portfolio construction configuration hash if needed." Portfolio-construction-level parameters (`top_n`, etc.) already have a home in the existing `parameter_hash`/`strategy_parameters` field — adding a second, near-duplicate hash for the same conceptual content would be unjustified complexity (directive §12 itself warns against refactoring "for architectural prettiness"). The composite-weighting scheme genuinely has no existing home (it describes neither a single factor nor a strategy parameter, but how multiple factors' outputs combine), so it alone gets a new field.

**Schema change and backward compatibility**: `signal_configuration_hash` is added as a **trailing field with a default value** (`signal_configuration_hash: str = "NOT_APPLICABLE"`) on both `ResearchRunIdentity` and `ResearchInputManifest`, following the exact precedent already used for `data_origin: str = "SYNTHETIC_DATA"` on every canonical contract since Phase 7H. A grep confirms 7 files construct these two dataclasses directly (`integrity_gate.py`, `store.py`, `real_data_verifier.py`, `live_provider_verifier.py`, `test_anti_fabrication_adversarial.py`, `test_research_replay_adversarial.py`, `test_research_run_store_immutability.py`); a defaulted trailing field means **none of them require modification** — only the Phase 8A gate path will ever set a real (non-default) value. `"NOT_APPLICABLE"` is chosen deliberately over an empty string or `None` so any future report can distinguish "single-factor run, no combination scheme" from "field simply wasn't populated."

**100% consistency guarantee**: because `factor_definition_hash` is computed from the exact `factor_definitions` list that `FactorRegistry.resolve()` consumed (§6), and `signal_configuration_hash` from the exact `signal_config` list `MultiFactorEngine` consumed, there is no code path where the identity's description and the actual execution can diverge — they are hashes of the literal objects passed to the executing code, not of a separate declaration.

---

## 16. `CertifiedResearchRunExecutor` Integration

Proposed control ordering (full detail in §4's diagram). Every new control fails closed:

| New control | Failure | Exception |
|---|---|---|
| Factor resolution | Unknown `factor_id` | `ValueError: FAIL CLOSED: unknown factor_id '{id}'` |
| Factor calculation | Required data source (market or fundamental) entirely absent for a requested factor | `ValueError: FAIL CLOSED: factor '{id}' requires {source} data, none supplied` |
| Normalization | Cross-sectional sample < 3 valid values | `ValueError: FAIL CLOSED: insufficient cross-sectional sample` |
| PIT (fundamental) | A symbol's only available fundamental record has `available_at > as_of` | Not a run failure — `FactorStatus.NOT_APPLICABLE` for that symbol (existing per-symbol semantics, consistent with how missing market data / delisted symbols are already handled per-symbol rather than failing the whole run) |
| Identity/hash mismatch | N/A at creation time (no prior value to mismatch against — this only applies at replay, §17) | — |
| Portfolio configuration | Currently no fail-closed condition proposed here — `PortfolioConstructor` already tolerates empty/degenerate weight sets by design (an empty portfolio is a valid, if uninteresting, research result) | — |
| Unlocked dataset / unverified provenance | Unchanged from Phase 7J | Unchanged |

---

## 17. Replay Architecture

`CertifiedReplayEngine.replay()` gains three new re-verification steps, inserted after its existing dataset/corporate-action re-verification (Phase 7J) and before delegating to `ResearchReplayEngine`:

```
1. Re-lock persistent dataset (unchanged, Phase 7I/7J)
2. Recompute corporate-action-adjusted series (unchanged, Phase 7J)
3. [NEW] Re-resolve factor_definitions via FactorRegistry
      → if a factor_id from the stored identity is no longer registered: FAIL CLOSED
        ("a factor this run depended on has been removed from the registry")
4. [NEW] Recompute FactorValue for every (factor, symbol) from the re-verified adjusted prices
   and re-supplied fundamental data (stored as a raw artifact at certification time, §18)
5. [NEW] Recompute normalization, composite score, signals, and raw portfolio weights
6. Reconstruct TransactionCostModel (unchanged, Phase 7J fix)
7. Compare recomputed portfolio weights against the ORIGINALLY STORED weights artifact:
      MATCH  → proceed to step 8 (this is "artifact mismatch" detection, distinct from step 9)
      MISMATCH → raise immediately: "FAIL CLOSED: recomputed portfolio weights diverge from
                 the certified artifact — factor/signal/portfolio computation is not reproducible"
8. Delegate to ResearchReplayEngine.replay_run() — re-executes BacktestEngine, recomputes result_hash
9. Compare result_hash: REPRODUCIBLE / MISMATCH (existing ReplayStatus enum, unchanged)
```

**Artifact mismatch vs. final result mismatch — handled distinctly, per directive §10's explicit requirement**:
- Step 7 (artifact mismatch) catches a break in the factor→signal→portfolio chain specifically — e.g., the `FactorRegistry`'s implementation for a given `factor_id` changed behavior without a version bump, or fundamental data was altered. This raises before ever reaching `BacktestEngine`, giving a precise diagnosis of *where* reproducibility broke.
- Step 9 (result mismatch, existing `ReplayStatus.MISMATCH`) is reserved for the case where factor/signal/portfolio weights recompute identically (step 7 passes) but the final backtest numbers still diverge — which would indicate a `BacktestEngine`/`TransactionCostModel` reproducibility bug, not a factor bug. Keeping these separate is a genuine diagnostic improvement over today's replay, which only ever reports one undifferentiated `MISMATCH`.

**Never reads old factor/signal/portfolio values and calls it reproducible**: steps 3–6 always recompute from source (re-verified dataset + re-supplied fundamental artifact + the *current* `FactorRegistry*), matching directive §10's explicit prohibition. The originally-stored weights (§18) are consulted **only** as a comparison target in step 7, never substituted for a fresh computation.

---

## 18. Artifact Model

Extending the existing `artifacts` dict written by `ResearchRunStore.create_run` (unchanged mechanism, new keys):

| Key | Content | Purpose |
|---|---|---|
| `daily_prices` (existing) | adjusted price series | unchanged |
| `raw_daily_prices` (existing) | raw price series | unchanged |
| `dates`, `dataset_directory`, `provider_data_origin` (existing) | unchanged | unchanged |
| **`fundamental_data`** (new) | canonical-serialized `Dict[str, List[FundamentalDataContract]]` as actually supplied | lets replay re-run PIT filtering + Value factor from the exact original inputs |
| **`factor_values`** (new) | `Dict[factor_id, Dict[symbol, FactorValue]]` at certification time | audit trail; also the step-7 comparison target's *inputs*, not itself trusted as the recomputation source |
| **`portfolio_weights`** (new) | the certified raw weights, pre-`PortfolioConstructor` | step-7 comparison target |

---

## 19. Failure / Fail-Closed Model

Every new failure mode listed in §16/§17 raises a `ValueError` (or, where an artifact is structurally missing, `FileNotFoundError`/`KeyError`, matching existing exception conventions from Phase 7A–7J) with a message prefixed `FAIL CLOSED:` — no new exception hierarchy is introduced, consistent with this codebase's existing convention of plain, greppable, explicit exceptions rather than a custom taxonomy.

---

## 20. Adversarial Test Matrix

| # | Directive requirement | Attack scenario | Expected | Test name (proposed) | Location |
|---|---|---|---|---|---|
| 1 | Factor definition changes | Change `window_days` param | `factor_definition_hash` differs | `test_1_factor_param_change_changes_hash` | `test_factor_engine_integration.py` |
| 2 | Factor hash changes | Same as #1 | Covered by #1 | — | — |
| 3 | Factor output changes | Same param change, real data | Momentum `FactorValue.raw_value` differs | `test_3_factor_param_change_changes_output` | same |
| 4 | Signal changes | Factor output change propagates | `SignalRecommendation.signal_score` differs | `test_4_signal_changes_with_factor` | same |
| 5 | Portfolio weights change | Signal change propagates | `PortfolioTarget.weights` differ | `test_5_weights_change_with_signal` | same |
| 6 | Backtest result changes | End-to-end, two different `factor_definitions` | `BacktestResult.total_return` differs | `test_6_backtest_result_changes_with_factor` | same |
| 7 | Unknown factor | `factor_id` not in registry | FAIL CLOSED | `test_7_unknown_factor_id_fails_closed` | same |
| 8 | Missing factor field | Fundamental factor, no fundamental data supplied for the whole run | FAIL CLOSED | `test_8_missing_required_data_source_fails_closed` | same |
| 9 | Future data | Fundamental record `available_at > as_of` | Excluded (`NOT_APPLICABLE`), not used | `test_9_future_fundamental_data_excluded` | same |
| 10 | Current-only fundamental data | `provenance == CURRENT_ONLY` | `FactorStatus.NOT_APPLICABLE`, not a valid historical value | `test_10_current_only_provenance_rejected` | same |
| 11 | Missing fundamental data | Symbol absent from `fundamental_data` | `NOT_APPLICABLE` for that symbol only | `test_11_symbol_missing_fundamental_data` | same |
| 12 | Universe mismatch | Delisted symbol requested | FAIL CLOSED (existing Control 4, re-confirmed under factor path) | `test_12_universe_mismatch_fails_closed` | same |
| 13 | Snapshot mismatch | Nonexistent snapshot | FAIL CLOSED (existing, re-confirmed) | `test_13_snapshot_mismatch_fails_closed` | same |
| 14 | Dataset mismatch | Uncertified dataset_version | FAIL CLOSED (existing, re-confirmed) | `test_14_dataset_mismatch_fails_closed` | same |
| 15 | Cost model mismatch | Different `commission_rate` | Measurable result difference (Phase 7J pattern, re-confirmed with real factor-driven weights) | `test_15_cost_model_drives_result_with_factors` | same |
| 16 | Hidden factor configuration | Attempt to pass a `factor_id` whose resolved parameters differ from what's hashed | Structurally impossible — hash is computed from the same object passed to `FactorRegistry.resolve()` (see §15); test proves this by construction | `test_16_identity_hash_matches_executed_config` | same |
| 17 | Hard-coded equal-weight bypass | Two different factor definitions on the same universe | Portfolio weights differ (proves equal-weight fallback is gone) | `test_17_no_hardcoded_equal_weight_fallback` | same |
| 18 | Replay factor recalculation | Tamper with fundamental data artifact between certification and replay | FAIL CLOSED at replay step 7 (artifact mismatch) | `test_18_replay_recomputes_factors_detects_tamper` | same |
| 19 | Replay portfolio recalculation | Same, verify weights (not just prices) are recomputed | FAIL CLOSED at replay step 7 | `test_19_replay_recomputes_portfolio` | same |
| 20 | Deterministic identical replay | Untampered run | `ReplayStatus.REPRODUCIBLE`, identical `result_hash` | `test_20_untampered_replay_is_reproducible` | same |

All 20 map to directive §11's list one-to-one (items 1/2 share one test since they're the same cause).

---

## 21. Backward Compatibility

- **228 existing tests**: none require modification. The new `signal_configuration_hash` field is defaulted (§15); no existing `ResearchRunIdentity`/`ResearchInputManifest` construction breaks. `BacktestEngine`, `PortfolioConstructor`, `CorporateActionAdjuster`, `TransactionCostModel`, `SimpleMomentumStrategy`, `FactorNormalizer`, `MultiFactorEngine`, `SignalEngine` are all reused **unmodified** — their existing unit tests are untouched.
- **Phase 7J's 25 integrity/bypass tests**: `test_integrity_gate_bypass_adversarial.py`'s existing tests construct `CertifiedResearchRequest` without the new `factor_definitions`/`fundamental_data`/`signal_config` fields. These three new fields must therefore also be defaulted (proposed: `factor_definitions: List[FactorSpec] = field(default_factory=list)`, empty meaning "no factor engine, hard-coded equal-weight" — **but see the explicit tension noted below**).
- **Explicit tension to resolve at implementation time, flagged here rather than silently decided**: if `factor_definitions` defaults to empty and empty means "fall back to equal-weight," Phase 7J's existing 25 tests keep passing unmodified, but the codebase still contains an equal-weight fallback path — which is precisely what directive §7 says to eliminate ("消除当前 CertifiedResearchRunExecutor 里的 hard-coded equal weight"). The alternative — making `factor_definitions` mandatory and non-empty always — is a clean architectural win but breaks all 25 of Phase 7J's existing bypass tests, which the directive's own §13 forbids weakening or deleting to get green tests. **This proposal recommends**: keep `factor_definitions` optional for backward compatibility, but rename the fallback path's behavior honestly — when empty, the gate uses `GenericFactorStrategy` with a trivial single "no-factor" mode is **not** proposed; instead, Phase 7J's 25 tests should be updated (not weakened — updated to supply a minimal real `factor_definitions`, e.g. single-factor momentum) as part of Phase 8A's own implementation, since directive §13 forbids weakening assertions but does not forbid updating test *setup* to match a deliberately-changed mandatory interface. **This is exactly the kind of decision the directive asks to flag rather than silently resolve — see Open Questions (§27).**

---

## 22. Data Provenance

No change to the `REAL_PROVIDER`/`LOCAL_PRODUCTION_VERIFICATION_DATA`/`GOLDEN_DATASET`/`SYNTHETIC_DATA` taxonomy. `fundamental_data` entries carry their own `data_origin` field (already on `FundamentalDataContract` since Phase 7A) and are validated the same way `provider_data_origin` is validated for market data today (§5 of Phase 7J's report) — extended to also check the fundamental data's own `data_origin` is one of the four recognized tags. `TUSHARE_TOKEN` remains unavailable; all Phase 8A test fixtures will use `GOLDEN_DATASET`/`SYNTHETIC_DATA`, never `REAL_PROVIDER`.

## 23. Security Considerations

No new secret-handling surface. `FactorRegistry` registration is code, not configuration-at-runtime, so no injection surface from `factor_id` strings beyond a dictionary lookup (unknown key → exception, not code execution). No new file I/O beyond the existing artifact-storage mechanism (§18), which already goes through `to_canonical_json`.

## 24. Performance Considerations

Cross-sectional normalization is O(universe size) per factor per rebalance date — unchanged complexity class from existing `FactorNormalizer`. No new N+1 query patterns are introduced since `fundamental_data`/`raw_price_series` remain caller-supplied dicts (in-memory), not per-symbol store queries. Not expected to be a concern at the dataset sizes this project currently exercises (tests use single-digit symbol counts).

## 25. Implementation Sequence

The directive's suggested 10-step sequence is sound; one adjustment recommended:

1. `FactorSpec`/`FactorDefinition` + `FactorRegistry` (+ `PITGate.filter_pit_fundamentals`)
2. `CertifiedResearchRequest` fundamental-data input field
3. Factor execution orchestration (Controls 7–8)
4. Normalization integration (Control 9, incl. new minimum-sample rule)
5. Signal integration (Controls 10–11)
6. **Resolve the Open Question in §21/§27 (factor_definitions optional vs. mandatory) before** portfolio construction integration — this decision changes whether step 7 also requires updating Phase 7J's existing test fixtures, which changes the step's scope materially. Recommend surfacing this to CEO for a decision at the start of implementation, not mid-way.
7. Portfolio construction integration (`GenericFactorStrategy` + Control 12–13, replacing hard-coded equal-weight)
8. `CertifiedResearchRunExecutor` full integration + identity binding (`signal_configuration_hash`)
9. Replay integration (`CertifiedReplayEngine` steps 3–7 from §17)
10. Adversarial tests (§20's 20 tests)
11. Full pytest regression + second read-only audit (unchanged Phase 7-series convention)

## 26. Risks

1. **Cross-sectional determinism under floating-point** (§12) — mitigated by canonical.py's existing 6-decimal rounding, but not zero-risk if a future factor introduces a numerically unstable calculation; recommend each new factor's PR include a determinism test (run twice, compare hash) as standing practice, not just for this phase.
2. **The optional-vs-mandatory `factor_definitions` tension** (§21) — the single biggest open design fork in this proposal; resolving it late risks rework.
3. **`GenericFactorStrategy` duplication vs. subclassing `SimpleMomentumStrategy`** — low risk, implementation-time detail, flagged in §14 for completeness.
4. **Fundamental data has no persisted warehouse** — by design for this phase (§10), but means Value-factor research runs are only as good as whatever fixture the caller supplies; this is an honest limitation to carry into the final report, not a blocker.

## 27. Open Questions (require CEO decision before/at implementation start)

1. **§21/§26.2**: Should `factor_definitions` be optional (preserving Phase 7J's 25 existing tests verbatim, but leaving an equal-weight fallback path in the codebase) or mandatory (fully eliminating the fallback, but requiring Phase 7J's 25 test *setups* — not their assertions — to be updated to supply a minimal factor config)? This proposal's default recommendation, if forced to choose: **mandatory**, with Phase 7J's test *fixtures* (not assertions) updated — because leaving any equal-weight fallback reachable from the certified path directly contradicts directive §7's explicit instruction, and updating a test's setup data (not weakening what it asserts) is expressly distinguished from "weakening" in directive §13's own wording. Awaiting explicit confirmation before implementation.
2. Minimum cross-sectional sample size (§12) proposed at 3 — arbitrary but conventional (smallest N for a meaningful std-dev-based statistic); confirm or adjust.
3. Should `GenericFactorStrategy` subclass `SimpleMomentumStrategy` or be an independent implementation of `BaseStrategy` with duplicated logic? No functional difference; CTO has no strong preference, defaults to independent implementation (avoids implying an inheritance relationship that doesn't conceptually exist — a generic strategy is not "a kind of" momentum strategy).

## 28. Acceptance Criteria

Adopts directive §16's checklist verbatim as the acceptance criteria for the eventual implementation phase; not repeated here to avoid drift between two copies of the same list. This proposal does not itself claim to satisfy any of them — it is a design document only.

---

**No code, tests, or data were modified to produce this document. `git status` remains clean except for this new file.**
