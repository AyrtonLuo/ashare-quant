# 🏛️ Corporate Action Unified Formula — Architecture Proposal
## Architecture Proposal Only — No Implementation

**Status**: PROPOSAL, REVISION 2 (CEO-scoped, final) — awaiting CEO approval to implement. No
production code, tests, dependencies, Replay, BacktestEngine, PIT, RIGHTS_OFFERING behavior, or
result hashing were modified to produce this document.
**Baseline**: `main` at `e100cda`. Re-confirmed before writing: `git status` clean,
`348 passed, 11 skipped, 0 failed`.
**Builds on**: the prior read-only audit turn, which ran the real `CorporateActionAdjuster.adjust()`
code path against `docs/CORPORATE_ACTION_SPECIFICATION.md`'s formula and found genuine numeric
divergence (up to ~5% relative, in a synthetic 10%-price-move scenario) — reproduced here only by
reference, not re-derived.

**Revision 2 — CEO scope decision**: approved for research/design: `CASH_DIVIDEND`,
`BONUS_ISSUE`, `RIGHTS_OFFERING`, same-`ex_date` combination handling, correct `P_pre` usage,
`adjustment_algorithm_version`. **Not approved: extending the unified formula to `STOCK_SPLIT`.**
`STOCK_SPLIT` remains an independent, untouched, unchanged factor — a separate future
architecture question, out of this proposal's scope. Revision 1's §3.1 `STOCK_SPLIT` extension
(the `×S` denominator term) is **withdrawn** from this revision accordingly; every section below
is updated to reflect a formula and implementation scoped to `D`/`B`/`R` only.

### Scope Confirmation (CEO's 9 required points, indexed to the section that answers each)

| # | Requirement | Answered in |
|---|---|---|
| 1 | Canonical formula: `P_ex = (P_pre - D + Pr×R) / (1 + B + R)` | §3.1 |
| 2 | How `P_pre` is determined | §3.1 |
| 3 | Why only `RIGHTS_OFFERING` combinations need the new joint-computation path | §2, §3.2 |
| 4 | How `adjustment_algorithm_version` enters Research Identity / Manifest | §4, §5 |
| 5 | How Replay recomputes using a historical run's own algorithm version | §4 |
| 6 | How old and new versions coexist | §4, §7 |
| 7 | No certified runs exist today → no migration needed | §7 |
| 8 | Full test matrix | §6 |
| 9 | `STOCK_SPLIT` is explicitly out of this proposal's scope | this section, §3.1, §8 |

---

## 1. Current State

`CorporateActionAdjuster._event_factor()` computes each event type's factor **independently**
against a single shared `reference_price` (the actual raw close **on/after** `ex_date`), then
`adjust()` **multiplies** the independent factors together for events sharing an `ex_date`. The
specification (`docs/CORPORATE_ACTION_SPECIFICATION.md` §2) instead defines one **unified**
fraction using `P_pre` (the price **before** `ex_date`):

```
P_ex = (P_pre - D + Pr·R) / (1 + B + R)          [spec — no S/STOCK_SPLIT term]
```

Zero certified runs exist today (`data/research/runs/` is empty; `golden_dataset_seed.py`
registers exactly one, single-type `CASH_DIVIDEND` action) — the divergence has **zero current
blast radius**, but is architecturally real and would corrupt any future certified backtest
spanning such a date.

---

## 2. Problem — Precisely Characterized (new finding, not in the prior audit turn)

Re-running the audit's numeric harness with `P_pre` substituted for `reference_price` (isolating
the two possible causes) proves the divergence has **exactly two independent, separable sources**:

**Source A — price-basis substitution.** `CASH_DIVIDEND` and `RIGHTS_OFFERING` use the observed
post-event price where the spec's formula wants the pre-event price. Affects every single-event
use of either type, and every combination that includes either.

**Source B — RIGHTS_OFFERING is the only type not multiplicatively separable.** Re-verified
algebraically and numerically: once `P_pre` replaces `reference_price`, **every combination that
does NOT include `RIGHTS_OFFERING`** — `dividend+bonus`, `dividend+split`, `bonus+split`,
`dividend+bonus+split` — becomes **exactly** equal to the unified formula (diff `0.0`, confirmed
by direct computation, not approximation). `STOCK_SPLIT` and `BONUS_ISSUE` have no price
dependency at all and are **always** byte-identical between the two approaches, single or
combined, with or without `RIGHTS_OFFERING` present. The divergence that survives Source A's fix
is confined **entirely** to combinations where `RIGHTS_OFFERING` co-occurs with any other type —
because `R` is the only variable appearing in **both** the numerator (`Pr·R`) and the denominator
(`1+B+R`) simultaneously, which a product of independent factors cannot reproduce.

This materially narrows the fix's true surface (§4).

---

## 3. Recommended Architecture

### 3.1 Canonical Algorithm

Adopt the specification's formula, unmodified, as canonical for all new certifications:

```
P_ex = (P_pre - D + Pr × R) / (1 + B + R)
```

`P_pre` is determined exactly as `adjust()` already determines its (currently misused) reference
price: `raw_prices[idx_before]`, where `idx_before` is the last index with `dates[i] < ex_date` —
an index the function **already computes** today; this is a substitution of *which* index's price
is read, not new lookup logic.

**`STOCK_SPLIT` — explicitly out of scope (CEO decision)**: `S`/`split_ratio` does not appear in
this formula and is not being extended into it. `STOCK_SPLIT`'s existing, unchanged factor
(`1/split_ratio`) continues to be computed and applied exactly as it is today — independently,
never as an input to the unified `D`/`B`/`R` computation — under both `"1.0"` and `"2.0"` (§4).
Whether/how to eventually fold `STOCK_SPLIT` into a fully unified formula remains a **separate,
independently-tracked future architecture question**, not part of this proposal or its
implementation.

### 3.2 Event Combinations — recommend a surgical fix, not a full rewrite

Because Source B (§2) is confined to `RIGHTS_OFFERING` combinations, two implementation shapes
are available:

| | **Option A (recommended): surgical** | Option B: uniform rewrite |
|---|---|---|
| Change | `_event_factor()`'s `CASH_DIVIDEND`/`RIGHTS_OFFERING` branches switch to `P_pre`. `adjust()` gains one new branch: if a `RIGHTS_OFFERING` event shares an `ex_date` with a `CASH_DIVIDEND` and/or `BONUS_ISSUE` event, compute one combined `D`/`B`/`R` factor via the unified formula instead of multiplying; otherwise, unchanged (multiply independent per-type factors, now already exact per §2). `STOCK_SPLIT`'s own factor is never part of this computation — see below. | Every `ex_date` group, regardless of composition, always computes via one unified-formula function (would require deciding how to fold in `S`, which is out of scope — an additional reason not to pursue this option now). |
| Blast radius | Small — `STOCK_SPLIT`/`BONUS_ISSUE`-only paths, and any non-`RIGHTS_OFFERING` combination, are untouched code, byte-identical behavior. | Touches every code path, including ones already provably correct. |
| Correctness | 100% spec-exact for every in-scope case (proven in §2, not just for the changed cases). | Not pursued (out of scope pending a `STOCK_SPLIT` decision this proposal doesn't make). |
| Re-test surface | `RIGHTS_OFFERING`-involving `D`/`B`/`R` combinations + both single-event price-basis changes. | N/A |

**Recommend Option A** — smallest change that achieves full correctness within the CEO-approved
scope, consistent with this project's established preference (Phase 9, RIGHTS_OFFERING) for the
minimal fix over a uniform rewrite when they're equally correct.

**`STOCK_SPLIT` composition rule (applies in all cases, both versions)**: if a `STOCK_SPLIT`
event shares an `ex_date` with any combination of `D`/`B`/`R` events, `STOCK_SPLIT`'s
`1/split_ratio` factor is computed independently exactly as today and **multiplied on top of**
whatever the `D`/`B`/`R` computation (single-type or the new combined path) produces — it is
never an input to the unified formula. E.g. `rights+split` = `unified_factor(D=0,B=0,R,Pr) ×
(1/split_ratio)`.

### 3.3 Combination Behavior Table (Option A, all verified by direct computation; `STOCK_SPLIT` rows show the composition rule above, not a new formula)

| Combination | vs. unified spec, once `P_pre` is used |
|---|---|
| single `CASH_DIVIDEND` | now exact (was off by Source A alone) |
| single `RIGHTS_OFFERING` | now exact (was off by Source A alone) |
| single `STOCK_SPLIT` | unchanged — always independent, out of scope |
| `dividend+bonus` | already exact — no combined-path needed |
| `dividend+bonus+split` | already exact for the `D`/`B` part; `split` multiplies on top unchanged — no combined-path needed |
| `dividend+rights` | needs the new combined-factor path (Source B) |
| `bonus+rights` | needs the new combined-factor path (Source B) |
| `rights+split` | new combined-factor path for `D`/`B`/`R`; `split` multiplies on top unchanged |
| `dividend+bonus+rights` (+ optional `split`) | needs the new combined-factor path (Source B) for `D`/`B`/`R`; any `split` present multiplies on top unchanged |

---

## 4. Versioning — Replay / Historical Results

**This is the load-bearing design decision.** A silent formula change would mean any future
certified run recomputes to a different `result_hash` on replay forever after — `Replay` would
report `FINAL_RESULT_MISMATCH` for results that were correctly certified under the algorithm
active at their creation time. That is incompatible with this project's certification-permanence
principle (the same principle Phase 9's `schema_version` and every `dataset_version`/
`snapshot_id` pinning already protects).

**Recommend**: a new trailing-defaulted field, `adjustment_algorithm_version: str = "1.0"`, added
to `ResearchInputManifest`/`ResearchRunIdentity` (mirrors Phase 9's `schema_version` precedent
exactly). `"1.0"` = today's per-event-independent-then-multiply behavior (preserved byte-for-byte,
dead code kept, never deleted). `"2.0"` = the unified formula (§3). `CertifiedResearchRunExecutor.
execute()` always stamps new runs `"2.0"`. `CertifiedReplayEngine.replay()` reads the run's own
**stored** `adjustment_algorithm_version` and passes that exact version into
`CorporateActionAdjuster.adjust()` — replay always recomputes under the algorithm the run was
*actually* certified with, never "whatever is current." `CorporateActionAdjuster.adjust()` gains
an `algorithm_version: str` parameter (no default — every caller must be explicit, so a future
version bump can't silently apply to an old call site).

This makes the versioning mechanism **general-purpose**, not a one-off patch: any future
adjustment-algorithm change reuses the same field and the same replay-pinning behavior.

**Explicitly rejected**: changing the formula without a version field. Today's zero-blast-radius
window makes this tempting, but it would leave no escape hatch for the *next* algorithm
correction — an unbounded, worsening reproducibility liability, not a one-time fix.

---

## 5. Data Model

- `CorporateActionContract`: **no new fields needed** — `cash_amount_per_share`, `bonus_ratio`,
  `split_ratio`, `rights_ratio`, `subscription_price` already carry everything the unified
  formula needs.
- `ResearchInputManifest` / `ResearchRunIdentity`: **one new trailing-defaulted field**,
  `adjustment_algorithm_version: str = "1.0"` (§4).
- `CorporateActionAdjuster`: `_event_factor(action, reference_price)` keeps its current signature
  and behavior for `STOCK_SPLIT` **unconditionally** (untouched under both versions, per §3.1 —
  out of scope) and for `BONUS_ISSUE` (price-independent, always byte-identical) and for
  `"1.0"`-pinned `CASH_DIVIDEND`/`RIGHTS_OFFERING` calls (byte-identical legacy path, using
  today's `reference_price`). A new function, e.g. `_combined_dbr_factor(events, p_pre) -> float`,
  implements §3's unified `D`/`B`/`R` formula for the `"2.0"` + `RIGHTS_OFFERING`-combined-with-
  `CASH_DIVIDEND`-and/or-`BONUS_ISSUE` case only — it never receives or considers `STOCK_SPLIT`
  events. `adjust()` gains: (a) computing `P_pre = raw_prices[idx_before]` alongside the existing
  `reference_price` computation (both already derivable from the already-computed `idx_before`),
  (b) an `algorithm_version` parameter threaded through, (c) one new branch: under `"2.0"`, if a
  `RIGHTS_OFFERING` event is present in an `ex_date`'s group alongside a `CASH_DIVIDEND` and/or
  `BONUS_ISSUE` event, call the new combined function for those events, then separately multiply
  in any `STOCK_SPLIT` event's independent factor exactly as today (§3.2's composition rule);
  otherwise (any single event, or any non-`RIGHTS_OFFERING` combination, under either version)
  proceed as today, with `CASH_DIVIDEND`/`RIGHTS_OFFERING` reading `P_pre` instead of
  `reference_price` when `algorithm_version=="2.0"`.

---

## 6. Test Plan

| Category | Tests |
|---|---|
| Single event | `CASH_DIVIDEND`/`RIGHTS_OFFERING` under `"2.0"` — new expected values using `P_pre` (will legitimately differ from the existing `"1.0"`-implicit test values — both retained, pinned by version). `STOCK_SPLIT`/`BONUS_ISSUE` under both versions — byte-identical, regression-only (confirms §3.1/§9's out-of-scope guarantee). |
| Pairwise (no rights) | `dividend+bonus`, `dividend+split`, `bonus+split` under `"2.0"` — assert exact equality to the independent-factor product (§3.3), proving Option A's "no combined-path needed" claim behaviorally, not just algebraically. |
| Pairwise (with rights) | `dividend+rights`, `bonus+rights` under `"2.0"` — assert exact equality to the unified `D`/`B`/`R` formula computed independently in the test. |
| Triple + scope boundary | `dividend+bonus+rights` — unified formula, exact match. `rights+split` and `dividend+bonus+rights+split` — assert the combined `D`/`B`/`R` factor matches the unified formula **and** the overall result equals that factor multiplied by `STOCK_SPLIT`'s unchanged independent factor (§3.2's composition rule) — this is the explicit regression proving `STOCK_SPLIT` was not folded into the unified computation. |
| Replay | A `"2.0"`-certified run with a rights-combination replays `REPRODUCIBLE` under `"2.0"`. A hand-constructed `"1.0"`-stamped run (same pattern as Phase 9's legacy-`schema_version` test) replays `REPRODUCIBLE` under `"1.0"`, using the **old** formula — proves version-pinning actually pins, not just defaults. |
| `result_hash` | Unchanged definition/computation point — existing `REPRODUCIBLE` tests continue passing unmodified; a new test asserts `result_hash`'s payload shape (`{"sharpe","return","mdd"}`) is untouched by this change. |
| Backward compatibility | A manifest with `adjustment_algorithm_version` absent (pre-dating this change) defaults to `"1.0"` and uses the legacy formula — never silently upgraded. All 14 existing `RIGHTS_OFFERING` tests and all existing `CASH_DIVIDEND`/`STOCK_SPLIT`/`BONUS_ISSUE` tests re-run **unmodified** and must continue passing (they exercise `"1.0"`-equivalent single-event/non-rights-combination behavior, per §3.3's table, so no expected value needs to change). |

---

## 7. Migration

**No certified runs exist today (`data/research/runs/` is empty, re-confirmed at this proposal's
baseline) — therefore no migration is required.** This is a factual state check, not a design
choice: there is nothing to move, nothing to re-certify, and no `"1.0"`-stamped historical result
to preserve compatibility for, because none exists.

- **New runs**: always certified under `"2.0"` going forward, the moment this is implemented.
- **If a `"1.0"`-era run ever exists in the future** (e.g. from a parallel branch or a restored
  backup): consistent with Phase 9's own "no lazy migration of old runs" decision, it keeps
  replaying correctly under `"1.0"` forever, unmodified; re-certifying it under `"2.0"` (if ever
  wanted) would be a separate, explicit, future decision, never automatic or silent.

---

## 8. Risks

1. **`adjust()`'s core loop gains a version parameter and a conditional branch** — low line-count,
   but it's shared by both the certified-execution and Replay call paths; requires the same full
   regression discipline as the `received_at` PIT change (audit real call chain, verify no hidden
   fallback).
2. **Version-field proliferation**: this adds a fourth versioned dimension to certification
   identity (alongside `dataset_version`, `snapshot_id`, `schema_version`) — manageable by
   precedent, but each addition raises the bar for a future implementer to get right.
3. **If real historical data with same-day `RIGHTS_OFFERING`+`CASH_DIVIDEND`/`BONUS_ISSUE`
   combinations is ever ingested**, the `"1.0"`/`"2.0"` numeric gap (confirmed up to
   several-percent relative, prior audit turn) becomes practically significant for any backtest
   spanning such a date — argues for implementing before real data exists (today's
   zero-blast-radius window), not after.
4. **`STOCK_SPLIT` remains a known, disclosed limitation, not a risk introduced here**: it stays
   on the pre-existing independent-multiply path under both algorithm versions (§3.1/§3.2). If a
   future directive later decides to fold `STOCK_SPLIT` into a fully unified formula, that will be
   its own proposal with its own versioning/testing — not a hidden dependency of this one.

---

## Final Report

**CORPORATE ACTION UNIFIED FORMULA — ARCHITECTURE PROPOSAL — REVISION 2 (FINAL, CEO-SCOPED)**

**Status**: PASS — design-only, incorporates the CEO's scope decision, ready for approval to
implement. No code, test, Replay, BacktestEngine, PIT, RIGHTS_OFFERING, or hashing changes made.

**Scope, as approved**: `CASH_DIVIDEND`, `BONUS_ISSUE`, `RIGHTS_OFFERING`, same-`ex_date`
combination handling among these three, correct `P_pre` usage, `adjustment_algorithm_version`.
**`STOCK_SPLIT` is explicitly excluded** — it stays on its current, unchanged, independent
multiplicative path under both algorithm versions; folding it into a unified formula is a
separate future architecture question, not part of this proposal (§3.1, §9 point 9).

**Canonical formula**: `P_ex = (P_pre - D + Pr×R) / (1 + B + R)`, adopted unmodified from
`docs/CORPORATE_ACTION_SPECIFICATION.md` — no extension. `P_pre = raw_prices[idx_before]`, an
index `adjust()` already computes today (§3.1).

**Why only `RIGHTS_OFFERING` combinations need the new path**: re-running the real
`CorporateActionAdjuster.adjust()` code path with `P_pre` substituted for `reference_price`
proved, by direct computation, that every combination of `CASH_DIVIDEND`/`BONUS_ISSUE` (with or
without `STOCK_SPLIT`, which stays independent regardless) is **already exactly equal** to the
unified formula once the price basis is fixed. Only `RIGHTS_OFFERING` — the sole variable
appearing in both the formula's numerator and denominator — is not multiplicatively separable
into independent factors, so only `RIGHTS_OFFERING`-combinations need the new joint-computation
code path (§2, §3.2).

**Versioning**: new `adjustment_algorithm_version` field (`"1.0"`/`"2.0"`) on
`ResearchInputManifest`/`ResearchRunIdentity`, mirroring Phase 9's `schema_version` precedent.
New certifications always stamp `"2.0"`. `CertifiedReplayEngine.replay()` reads each run's own
stored version and recomputes under that exact algorithm — never "whatever is current" — so
certification permanence is preserved as a durable, general-purpose guarantee (§4).

**Old/new coexistence**: `"1.0"` (today's per-event-independent-then-multiply behavior) is
preserved byte-for-byte as dead code, never deleted; `"2.0"` is the unified `D`/`B`/`R` formula.
`CorporateActionAdjuster.adjust()` takes an explicit `algorithm_version` parameter with no
default, so no call site can silently drift onto a version it didn't request (§4, §5).

**Migration**: none required — no certified runs exist today (`data/research/runs/` empty,
re-confirmed); nothing to move or re-certify (§7).

**Testing**: full matrix specified (§6) — single-event, pairwise (with/without rights), triple +
an explicit scope-boundary test proving `STOCK_SPLIT` is never folded into the unified
computation, Replay under both versions, `result_hash` stability, and backward compatibility (all
14 existing `RIGHTS_OFFERING` tests plus existing `CASH_DIVIDEND`/`STOCK_SPLIT`/`BONUS_ISSUE`
tests must pass unmodified).

**Risks**: four identified (§8), none blocking; `STOCK_SPLIT` is recorded as a known, disclosed,
out-of-scope limitation rather than an open risk of this proposal.

**Production Impact**:
```
Production Code Modified: NO
Tests Modified: NO
Dependencies Modified: NO
Commit Created: pending this commit (proposal document only)
Push Performed: NO
```

**Recommendation**: **READY FOR CEO APPROVAL TO IMPLEMENT.**
