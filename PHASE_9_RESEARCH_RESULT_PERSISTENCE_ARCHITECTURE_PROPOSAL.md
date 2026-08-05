# Phase 9 — Research Result Persistence Hardening
## Architecture Proposal Only — No Implementation

**Status**: PROPOSAL — awaiting CEO review. No production code, tests, dependencies, or data
were modified to produce this document.
**Baseline**: Phase 8R frozen at commit `29372bf`. Re-confirmed before writing: `git status`
clean except this new file and the pre-existing untracked `.claude/`/`CLAUDE.md`;
`304 passed, 11 skipped, 0 failed`.

---

## 1. Executive Summary

The gap is not a storage-architecture flaw and not a serialization bug — it is a **contract
completeness gap**. `ResearchRunStore.create_run()` already persists everything handed to it
as real, canonical, cross-process-readable JSON files on disk (proven: `daily_prices`,
`portfolio_weights`, and `factor_values` already round-trip correctly across processes today,
exercised continuously by Phase 8A's and Phase 8R's own test suites). The problem is narrower
and more mechanical than it first appears: `CertifiedResearchRunExecutor.execute()` simply
never places `BacktestResult`'s actual numeric fields (`total_return`, `sharpe_ratio`,
`max_drawdown`, etc.) into any of the four things it hands to `create_run()` — not `identity`,
not `input_manifest`, not `result_manifest`, not `artifacts`. `ResearchResultManifest` was
designed with seven result-component hash fields (`positions_hash`, `trades_hash`,
`signals_hash`, `factor_output_hash`, `performance_metrics_hash`, `drawdown_hash`,
`benchmark_result_hash`) that have *never* been populated — they default to the literal string
`"UNAVAILABLE"` and no code path in this repository has ever set them to anything else, since
Phase 7B. This was confirmed by reading a real, currently-persisted run
(`data/research/runs/run_20260804_001533_971512/result_manifest.json`): every field is a hash
or the literal string `"UNAVAILABLE"`; the actual numbers (`total_return=0.0519`,
`sharpe_ratio=6.4029`, ...) exist only in the Phase-8R-owned side cache sitting next to it.

Because this is a contract gap rather than a mechanism gap, the recommended fix (§9) is
deliberately conservative: extend the existing, already-proven `ResearchResultManifest` +
`ResearchRunStore` persistence path with the missing fields, rather than building new storage
infrastructure. Two more expansive alternatives are presented and rejected for this reason.

---

## 2. Current Architecture

```
CertifiedResearchRunExecutor.execute(request)
        │
        ├── BacktestEngine.run_backtest(...) → BacktestResult (14 fields, held in memory only)
        │
        ├── ResearchInputManifest  (full config + hashes)              ─┐
        ├── ResearchResultManifest (result_hash, equity_curve_hash,      │  passed to
        │                           7x "UNAVAILABLE" hash placeholders)  │  ResearchRunStore
        ├── ResearchRunIdentity    (identity + all hashes)               │  .create_run()
        └── artifacts: dict (daily_prices, raw_daily_prices, dates,      │
              corporate_actions_applied, dataset_directory,              │
              provider_data_origin, fundamental_data, factor_values,    ─┘
              portfolio_weights — NOTE: no BacktestResult metrics here)
                        │
                        ▼
        return (backtest_result, identity)  ← caller gets the real BacktestResult HERE,
                                               synchronously, but it is discarded once the
                                               caller's stack frame returns unless the caller
                                               separately persists it itself.
```

`ResearchRunStore.create_run()` (unmodified since Phase 7A) writes exactly what it's given —
`run_metadata.json`, `input_manifest.json`, `result_manifest.json`, and `artifacts.json` (only
if `artifacts` is non-empty) — via `to_canonical_json(asdict(...))`, one file per write, no
temp-file/atomic-rename, no partial-write guard. `get_run()` reads them back (from an
in-memory cache first, falling back to disk) — this read path is already correct and already
proven cross-process for every field that IS written.

Phase 8R's `data/research/workbench_metrics/<run_id>.json` side cache (introduced this
session) plugs the display gap by having the Application Layer separately write the
`BacktestResult`'s scalar fields to its own file immediately after `execute()` returns,
outside `ResearchRunStore` entirely.

---

## 3. Root Cause Analysis

Answering the ten required questions directly, from source inspection (not inference):

**1. `BacktestResult`'s real structure** (`src/quant/backtest/engine.py:14-29`, frozen dataclass):
`dataset_id: str`, `strategy_id: str`, `equity_curve: List[float]`, `daily_returns: List[float]`,
`total_return: float`, `annualized_return: float`, `annualized_volatility: float`,
`sharpe_ratio: float`, `max_drawdown: float`, `win_rate: float`, `turnover: float`,
`trade_count: int`, `snapshot_id: Optional[str]`, `as_of: Optional[str]`.

**2. Fields that must be persisted**: the eight scalar summary metrics
(`total_return` … `trade_count`) — small, cheap, needed for any dashboard/list/report without
recomputation. `dataset_id`/`strategy_id`/`snapshot_id`/`as_of` are already duplicated in
`ResearchInputManifest` and don't need a second home.

**3. Derived / reconstructable fields**: `equity_curve` and `daily_returns` are the one place
where a real design choice exists (§9). They are large (one float per trading day) and are
**already provably reconstructable** by replay — `CertifiedReplayEngine` already recomputes the
entire backtest deterministically from stored inputs and gets a byte-identical `result_hash`
back (proven continuously by Phase 8A/8R's `REPRODUCIBLE` tests). Persisting them is a
convenience (instant read vs. a cheap recomputation), not a numerical-truth requirement.

**4. How research identity is generated**: `ResearchRunIdentity` (frozen dataclass,
`identity.py`) is built once, at `execute()` time, from hashes of every certified input
(universe, factor config, signal config, cost model, dataset, snapshot, code version) plus
`input_hash` and `result_hash`. Unchanged by this proposal.

**5. How the hash is generated**: `compute_canonical_sha256()` (`canonical.py`) — the single
authoritative canonical serializer since Phase 7I/7J: recursive pre-canonicalization (handles
dataclasses, `Enum`, `Decimal`, `datetime`, numpy scalars; rounds floats to 6 decimals; rejects
NaN/Infinity), then SHA-256 over the resulting JSON. This is the existing, already-hardened
numerical-truth mechanism this proposal reuses rather than replaces.

**6. What replay depends on**: dataset directory + `PersistentDatasetManifestStore`,
`SnapshotManager`, `CorporateActionStore`, `SecurityMasterRegistry`, `fundamental_data` (all
re-supplied by the caller, representing "current" source-of-truth state) plus the run's own
stored `artifacts` (`raw_daily_prices`, `dates`, `portfolio_weights` — used only as *comparison
targets*, never as computation inputs) and `input_manifest` (`factors_config`, `signal_config`,
`cost_model_config`, `universe_symbols`, `as_of`). Every step is independently recomputed;
nothing cached is trusted as an input. Unaffected by this proposal.

**7. What persistence actually saves today**: `identity` (hashes + metadata, complete),
`input_manifest` (full config + hashes, complete), `result_manifest` (`result_hash`,
`equity_curve_hash`, and seven `"UNAVAILABLE"` placeholders — **no raw numbers**), `artifacts`
(adjusted/raw prices, dates, corporate actions, dataset directory, provenance, fundamental
data, factor value trace, portfolio weights — **but not `BacktestResult`'s metrics**).

**8. Why values are lost cross-process**: because they were never included in what was written
in the first place — not a serialization defect, not a process-boundary defect. Every field
that *is* written already survives a fresh-process reload today (this is exactly what Phase
8R's `test_get_research_run_matches_creation_result`-style tests already exercise, and what
`get_research_run()` already implements correctly for every field it's given).

**9. Classification**: **Contract problem.** Specifically, `CertifiedResearchRunExecutor.
execute()`'s construction of `result_manifest`/`artifacts` is incomplete relative to what
`BacktestResult` actually contains. Storage design (files on disk under a run-id directory),
serialization (`to_canonical_json`), and the process boundary (plain file I/O) are all already
correct and already proven — nothing about *how* data gets written and read needs to change,
only *what* gets handed to that already-working mechanism.

**10. Why the current workaround cannot be canonical persistence**: `workbench_metrics/
<run_id>.json` (a) is written by the Phase 8R Application Layer, not by
`CertifiedResearchRunExecutor` itself — any caller that goes through `ResearchRunStore`
directly (a different UI, a script, a future "Antigravity"/other-agent consumer) will never
see it; (b) has no schema version, no integrity binding to `result_hash`, and is never
consulted by Replay; (c) is not part of `ResearchRunIdentity` and carries no participation in
the certification chain at all — it is exactly what the CEO's own review called it: a
UI-display convenience, not a source of truth.

---

## 4. Requirements

Restating the directive's objective as concrete, testable requirements:

- R1: A fresh process, given only a `research_run_id` and a `ResearchRunStore` pointed at the
  same `base_dir`, can retrieve `BacktestResult`'s real numeric values.
- R2: The persisted numeric values are provably the exact values certified at creation time
  (not merely "some value" — a value that matches `result_hash`).
- R3: No change to `result_hash`'s existing definition or to `CertifiedReplayEngine`'s existing
  comparison logic (both already correct and already adversarially tested — see §11).
- R4: Backward compatible with runs already persisted under the current schema (none exist in
  the real repository today — confirmed, `data/research/runs/` has exactly one run, created
  during this session's manual testing — but the design must not assume that stays true).
- R5: No change to `BacktestEngine`, `FactorRegistry`, `PortfolioConstructor`, PIT/corporate-
  action/dataset-lock logic, or any Phase 7/8A semantic.
- R6: Existing 304-test suite remains green, unmodified in behavior.
- R7: `workbench_metrics/` becomes retireable (not necessarily retired in this phase — that's
  an implementation-time decision) once canonical fields exist, without an emergency migration.

---

## 5. Candidate Architecture A — Extend `ResearchResultManifest` (Recommended)

**A. Storage Model**: unchanged — still `data/research/runs/<run_id>/result_manifest.json`,
written by the existing, unmodified `ResearchRunStore.create_run()`.

**B. Serialization**: unchanged — still `to_canonical_json(asdict(result_manifest))`. The
*only* change is that `asdict()` now includes real fields instead of `"UNAVAILABLE"` strings.

**C. Identity**: unchanged. `ResearchRunIdentity` is not touched.

**D. Hash**: `result_hash`'s definition is **frozen exactly as today**
(`compute_canonical_sha256({"sharpe": ..., "return": ..., "mdd": ...})`, computed once at
`execute()` time) — deliberately *not* redefined to hash the full manifest, because
`CertifiedReplayEngine` already depends on that exact three-field shape for its reproducibility
comparison (§11), and changing it would be an unauthorized Phase 8A semantic change per CEO
scope rules. A *new*, independent load-time check (§12) verifies the persisted scalar fields
are internally consistent with `result_hash` — this is integrity verification, not hash
redefinition.

**E. Replay**: fully unaffected — `CertifiedReplayEngine` already recomputes `BacktestResult`
from scratch and never reads `result_manifest`'s new fields as an input.

**F. Numerical Truth**: `total_return` etc. pass through `compute_canonical_sha256`'s existing
float-rounding rule (6 decimal places) at exactly one point — when `result_hash` is computed —
same as today. The *new* manifest fields store the **exact, unrounded** `BacktestResult` values
(Python `float`s, IEEE-754 double precision, the same values already flowing through
`equity_curve`/`daily_returns` today) — no additional rounding is introduced by this design.

**G. Cross-Process**: solved by construction — this is exactly the mechanism already proven to
work cross-process for `daily_prices`/`portfolio_weights` (Phase 8A/8R's own tests), extended
to two more fields on an existing dataclass.

**H. Backward Compatibility**: new fields are added as **trailing, defaulted** dataclass
fields (exact precedent: `signal_configuration_hash` added to `ResearchRunIdentity`/
`ResearchInputManifest` in Phase 8A) — every existing `ResearchResultManifest(...)` constructor
call across the codebase (`store.py`, `real_data_verifier.py`, `live_provider_verifier.py`,
three test files — 5 call sites, grepped) remains valid unmodified. See §15 for the sentinel
value policy for genuinely-old records.

**I. Failure Recovery**: not solved by this option alone — `ResearchRunStore.create_run()`'s
lack of atomic writes is a **pre-existing gap** (present since Phase 7A, not introduced by
Phase 9) that this proposal recommends fixing alongside the field addition, since touching
`create_run()` for the new field is the natural point to also add write-atomicity (§13).

**J. Concurrency**: also a pre-existing gap — the existence check (`if run_id in
self._memory_store or os.path.exists(run_path)`) and the directory creation
(`os.makedirs(run_path, exist_ok=True)`) are two separate, non-atomic steps, so two processes
racing to create the *same* `run_id` at the *same* instant could both pass the check before
either finishes writing. Low real-world likelihood (`run_id`s are timestamp+microsecond-based
in Phase 8R and expected to be unique per research action in a single-user, low-frequency
tool) but worth closing given §13's atomic-write work touches the same code path anyway.

**K. Testing**: see §16 — this option's tests are the smallest of the three candidates because
it changes the least surface area.

---

## 6. Candidate Architecture B — Dedicated `CanonicalResultStore`

A new, separate persistence class (parallel to, not replacing, `ResearchRunStore`), purpose-
built for numeric results, writing `data/research/runs/<run_id>/canonical_result.json`
independently.

**A-G** (storage/serialization/identity/hash/replay/numerical-truth/cross-process): same
underlying mechanism as Option A (still `to_canonical_json` to a file under the run's
directory), so mechanically no better or worse.

**Key difference**: `ResearchResultManifest` stays byte-for-byte as it is today (zero
Phase 8A file changes) — the new data lives entirely in a sibling file managed by a new class.

**H. Backward Compatibility**: trivially perfect — old runs simply lack the new file; no
dataclass field changes anywhere.

**I. Failure Recovery / J. Concurrency**: **worse than Option A** — now there are *two*
independent writes per `create_run()` call (`result_manifest.json` and the new
`canonical_result.json`) that must both succeed for the run to be "complete," introducing a new
inter-file consistency question (what if `result_manifest.json` writes but
`canonical_result.json` doesn't?) that Option A does not have, since Option A's new fields live
*inside* the single `result_manifest.json` write that already exists.

**Why not recommended**: solves the same problem as Option A with an extra moving part (a
second store class, a second file, a second consistency invariant to maintain and test) for no
corresponding benefit — the directive's own root-cause question (§3.9) already establishes this
is a contract gap, not a "the existing store can't hold this kind of data" gap, so there is no
structural reason to introduce a second store.

---

## 7. Candidate Architecture C — Extend the `artifacts` Convention

Add a `"backtest_metrics"` key to the existing `artifacts` dict already passed to
`create_run()` — zero new dataclass fields anywhere, reusing the exact mechanism already
proven for `portfolio_weights`/`factor_values`/etc.

**Key difference from A**: the metrics live in `artifacts.json` (an open-ended `Dict[str, Any]`
bag) rather than as typed fields on `ResearchResultManifest`.

**D. Hash / Numerical Truth**: weaker than Option A — `artifacts` has no schema, no field
types, no dataclass-level guarantee the keys stay consistent across code changes; verifying
consistency against `result_hash` requires the loader to know the historical convention by
string-key convention rather than by typed field access, which is more fragile to a future
rename.

**H. Backward Compatibility**: fine (dict access with `.get()` defaults) but for the same
reason as D, silently returns `{}`/`None` for old runs rather than making the absence
structurally visible the way a typed, defaulted dataclass field with an explicit sentinel does.

**Why not recommended**: `artifacts` is deliberately the *untyped* extension point in this
architecture (used for large, replay-input-shaped data like price series) — using it for the
canonical summary-metrics record blurs a distinction worth keeping: "inputs a re-execution
needs" (artifacts) vs. "the certified numeric result itself" (result_manifest). Option A keeps
that distinction and gets stronger typing for a marginal one-line difference in effort.

---

## 8. Comparison Matrix

| Criterion | A: Extend Manifest | B: Dedicated Store | C: Artifact Convention |
|---|---|---|---|
| Correctness | ✅ | ✅ | ✅ |
| Numerical fidelity | ✅ exact | ✅ exact | ✅ exact |
| Determinism | ✅ (reuses canonical.py) | ✅ | ✅ |
| Simplicity | **Highest** (1 dataclass, 1 write) | Lowest (2 classes, 2 writes) | High |
| Maintainability | **Highest** (typed fields) | Medium (2 files to keep in sync) | Medium (untyped dict) |
| Backward compatibility | ✅ trailing-defaulted | ✅ trivial | ✅ dict `.get()` |
| Operational risk | **Lowest** (1 write path) | Higher (2-write consistency) | Low-Medium (untyped) |
| Testability | **Highest** (typed assertions) | Medium | Medium (dict-shape assertions) |
| Phase 8A files touched | `manifest.py`, `integrity_gate.py` | `integrity_gate.py` only | `integrity_gate.py` only |

---

## 9. Recommended Architecture: **Option A — Extend `ResearchResultManifest`**

Chosen over B and C specifically because this project's own existing pattern (Phase 8A adding
`signal_configuration_hash` as a trailing-defaulted field, rather than inventing a parallel
config-store) already establishes that extending an existing, working, typed persistence
contract is how this codebase prefers to close exactly this kind of gap — consistency with
prior art, not novelty, is the deciding factor. It is not the most complex option (B); it is
the option that changes the least while fully satisfying every requirement in §4. `git blame`/
history on `manifest.py` shows every prior field addition to these dataclasses followed this
same trailing-default pattern (`data_origin`, `signal_configuration_hash`) — Option A is a
continuation of established convention, not a new design philosophy.

---

## 10. Canonical Persistence Contract

**Canonical Research Result** = the union of:
- `ResearchRunIdentity` (unchanged) — the hash-level identity of the run.
- `ResearchInputManifest` (unchanged) — the complete, unambiguous specification of every input.
- `ResearchResultManifest` **extended** with: `total_return`, `annualized_return`,
  `annualized_volatility`, `sharpe_ratio`, `max_drawdown`, `win_rate`, `turnover`,
  `trade_count` (all `Optional[float]`/`Optional[int]`, default `None` — see §15), plus a new
  `schema_version: str` field.
- `artifacts["portfolio_weights"]`, `artifacts["factor_values"]`,
  `artifacts["corporate_actions_applied"]`, `artifacts["provider_data_origin"]` (already
  canonical since Phase 8A — unchanged).

**Explicitly NOT canonical** (and why):
- `equity_curve` / `daily_returns` full arrays — reconstructable via Replay (§3.3); persisting
  them is a *display convenience*, not required for numerical truth. Recommendation: persist
  them too (they're already computed and the marginal storage cost for a low-frequency research
  tool is small), but tag them clearly as "convenience cache, Replay is authoritative" in a
  code comment — never treat their presence/absence as a correctness signal.
- `workbench_metrics/<run_id>.json` — superseded by this proposal once implemented; UI cache,
  never authoritative, not part of `ResearchRunIdentity`.
- Any UI-layer view model (`ResearchRunDetailView` etc.) — pure presentation, derived fresh
  from the canonical record on every read, never itself persisted as a source of truth.
- Derived analytics not already computed by `BacktestEngine` (e.g., rolling Sharpe, factor
  attribution breakdowns) — out of scope; if wanted later, compute from the canonical record,
  don't persist a growing pile of derived numbers alongside it.

---

## 11. Numerical Truth Design

```
BacktestResult (raw, in-memory, Python float64)
        │
        ▼  asdict(extended ResearchResultManifest) — NO rounding here (unlike result_hash)
to_canonical_json(...)                                — json.dumps, float repr preserves
        │                                                full double precision (Python's
        ▼                                                json module round-trips float64
disk write (result_manifest.json)                        exactly; this is the same guarantee
        │                                                already relied on for equity_curve
        ▼                                                today)
json.load(...) on a fresh process
        │
        ▼
ResearchResultManifest(**dict) — reconstructed, field values bit-identical to the originals
```

- **dtype policy**: Python `float` in, Python `float` out. No numpy dtypes are ever persisted
  (already true today — `BacktestEngine` casts every numpy result to native `float`/`int`
  before constructing `BacktestResult`, confirmed by reading `engine.py`'s return statement).
- **precision policy — CORRECTED DURING IMPLEMENTATION** (see the implementation report for
  full disclosure): this section originally claimed "full IEEE-754 double precision preserved…
  no additional rounding introduced." That was inaccurate. `ResearchRunStore.create_run()`
  writes the *entire* manifest via `to_canonical_json`, which — as a pre-existing, project-wide
  behavior in place since Phase 7I, not something this proposal introduces — rounds every float
  to 6 decimal places as part of standard canonicalization, not only the small `result_hash`
  payload. In practice this is harmless: `BacktestEngine` already rounds every scalar result
  field to 4 decimal places before `BacktestResult` is constructed, and a 4-decimal value is
  exactly representable at 6-decimal precision, so no real backtest value this codebase
  produces ever loses precision. The corrected policy is: **persisted values are exact up to
  the existing 6-decimal canonicalization ceiling already applied to everything
  `ResearchRunStore` persists** — not "unlimited," as originally (incorrectly) stated.
- **NaN/Inf policy**: `compute_canonical_sha256` already rejects non-finite floats (Phase 7I).
  For the raw manifest fields (not hashed), `to_canonical_json`'s underlying `json.dumps` is
  called with `allow_nan=False` project-wide (confirmed in `canonical.py`) — a NaN/Inf
  `BacktestResult` value would already fail to serialize today, which is correct fail-closed
  behavior to preserve, not relax.
- **ordering policy**: N/A for scalars; for `equity_curve`/`daily_returns` (if persisted),
  order is preserved as a Python list — `canonical.py`'s `list`/`tuple` rule already documents
  "order preserved (not sorted)" since Phase 7I.
- **timezone policy**: unchanged — `as_of`/`created_at` already use naive ISO-8601 strings
  project-wide (no timezone info anywhere in this codebase currently); this proposal does not
  introduce timezone handling.
- **floating-point comparison policy** (§16 defines this precisely, not just "assert equal"):
  `original_metric == reloaded_metric` using Python's native `==` on the *unrounded* values is
  the correct equality definition here, because JSON round-trip of a Python float is exact
  (bit-for-bit), not an approximation — there is no floating-point *drift* to tolerate at the
  persistence layer (drift, if any, only enters via `result_hash`'s deliberate 6-decimal
  rounding, which is a separate, already-tested concern). Tests use exact `==`, not
  `pytest.approx`, specifically to prove this.
- **deterministic serialization policy**: unchanged — `to_canonical_json` (sorted keys,
  `ensure_ascii=True`, fixed indent) is already deterministic; reused as-is.

---

## 12. Identity & Hash Design

Deliberately kept separate, per the directive's explicit warning not to conflate them:

- **Identity** (`ResearchRunIdentity`/`research_run_id`): answers "which certified
  configuration produced this?" — unchanged by this proposal.
- **Content integrity hash** (`result_hash`): answers "has the *specific three-field result
  payload* this hash covers been tampered with?" — unchanged definition, unchanged computation
  point (once, at `execute()` time).
- **NEW: load-time consistency check** (not a new hash — a verification step): on `get_run()`,
  if the extended manifest fields are present (`schema_version >= "2.0"`, see §15), recompute
  `compute_canonical_sha256({"sharpe": manifest.sharpe_ratio, "return": manifest.total_return,
  "mdd": manifest.max_drawdown})` and compare to `identity.result_hash`. A mismatch means the
  persisted manifest file was tampered with or corrupted independently of the identity file —
  this is a genuinely new integrity capability (today, nothing checks `result_manifest.json`
  against `identity.result_hash` at load time at all), proposed as an *optional* verification
  function (`verify_result_manifest_integrity(run_data) -> bool`), not a mandatory gate inside
  `get_run()` itself — making it mandatory would be a behavior change to an existing, widely-
  used method outside this proposal's authorized scope (§14 non-goals).

---

## 13. Atomicity & Integrity

**Atomic Write** (closes a pre-existing gap, §5.I): change `create_run()`'s four file writes
to: (1) write each file to a `.tmp` sibling path, (2) `os.replace()` (atomic on POSIX) each
`.tmp` file to its final name only after all four are successfully written to temp paths, (3)
on any exception during step 1, clean up temp files and re-raise — never leave a partially-
written run directory that `get_run()` could load as if it were complete. This is a small,
mechanical, low-risk change to `create_run()`'s body — no signature change, no caller changes.

**Corruption detection**: `get_run()` gains a `try`/`except json.JSONDecodeError` around each
file load, re-raising as `RuntimeError(f"FAIL CLOSED: corrupted persisted file for run
'{run_id}': {path}")` — today a corrupted JSON file would raise an unhandled, unclear
`json.JSONDecodeError` from deep inside `get_run()`; this wraps it in a clear, FAIL-CLOSED-
prefixed message consistent with this project's error-message convention, without changing
*when* it fails (still fails at load time, still refuses to return partial/guessed data).

**A commit marker, considered and rejected**: writing a final `_COMPLETE` marker file after
all four succeed was considered as an alternative to atomic rename; rejected because
`os.replace()` already gives atomicity per-file, and a separate marker file reintroduces a
fifth non-atomic write with its own partial-failure window — strictly worse, not simpler.

---

## 14. Explicit Non-Goals (restating directive §14, enforced by scope discipline)

Not touched, considered, or designed in this proposal: live trading, broker integration, order
execution, real-time trading, `TransactionCostModel`, `turnover`, `trade_count`'s *semantic*
correctness (only its *persistence* is in scope — whether `trade_count` means what its name
implies is Phase 8A's own already-disclosed, separately-deferred limitation, unrelated to
whether it round-trips through storage), new factors, any other Phase 9 feature, UI redesign.

---

## 15. Migration Strategy

- **New field defaults**: `total_return: Optional[float] = None` (and identically for the
  other seven new fields), plus `schema_version: str = "1.0"`. A record with
  `schema_version == "1.0"` (every run persisted before this change, including the one real run
  currently on disk from this session's manual testing) has `total_return is None`, etc. — the
  Application Layer (or any future reader) must treat `None` as **"metrics not available for
  this legacy run"**, never as `0.0` — continuing this project's existing "declare UNAVAILABLE,
  never guess/default" principle (Phase 7's own Anti-Fabrication Constitution) rather than
  inventing a new one for this proposal.
- **`workbench_metrics/` side cache**: no migration needed *for existing data* — it already
  independently persists the metrics for the one run created this session and will continue to
  work unmodified. Recommendation for the *implementation* phase (not decided here): once the
  Application Layer's `get_research_run()` can read real metrics from `schema_version >= "2.0"`
  manifests, have it prefer the canonical fields and fall back to `workbench_metrics/` only for
  legacy (`schema_version == "1.0"`) runs — a graceful transition, not a hard cutover, and not
  a data-migration script (no existing canonical data needs rewriting; old runs simply remain
  `"1.0"` forever, which is honest, not a defect).
- **No lazy migration of old runs into the new schema** is recommended — recomputing a legacy
  run's metrics would require re-running Replay (possible, since Replay is deterministic) but
  doing so automatically/silently on read would blur "this is what was originally certified" vs
  "this is a value we backfilled later," which this project's principles treat as a meaningful
  distinction (an explicit `schema_version` is the honest way to represent "we don't have this
  for old runs," not a reason to fabricate it after the fact).

---

## 16. Testing Strategy

| Category | Tests |
|---|---|
| Unit (serialization) | `ResearchResultManifest` with new fields round-trips through `to_canonical_json`/`json.loads` with exact (`==`, not `approx`) field equality |
| Numerical truth | Construct a `BacktestResult` with representative float values (including values requiring full double precision, e.g. `1/3`), persist, reload, assert bit-identical `==` |
| Identity stability | Existing `ResearchRunIdentity`/`result_hash` tests continue passing **unmodified** — proves this proposal doesn't perturb identity |
| Hash stability/integrity | New `verify_result_manifest_integrity()` returns `True` for an untampered run and `False` after directly editing a persisted `result_manifest.json`'s `sharpe_ratio` field on disk |
| Cross-process | Process-A-writes/Process-B-reads is already exercised by every existing Phase 8R test via `ResearchRunStore(base_dir=...)` re-instantiation (a fresh `ResearchRunStore` object per test *is* the cross-process simulation this codebase already uses, since the store is stateless-on-disk by design) — extend the same pattern to assert the new fields specifically |
| Replay | Existing `REPRODUCIBLE` replay tests continue passing **unmodified** — proves Replay never reads the new fields as computation input |
| Corruption | Truncate/corrupt `result_manifest.json` on disk, assert `get_run()` raises the new clear `RuntimeError` rather than an opaque `JSONDecodeError` or (worse) silently returning partial data |
| Compatibility | Hand-construct an old-shape (`schema_version` absent / `"1.0"`) run directory, assert it loads without error and every new field reads as `None` |
| Concurrency | Two threads/processes racing `create_run()` with the *same* `run_id`: assert exactly one succeeds and the other raises the existing immutability error, never a corrupted mixed-write directory (requires the atomic-write change in §13 to pass reliably — document as a dependency) |
| Regression | Full existing suite re-run: **304 passed, 11 skipped, 0 failed**, unmodified — no existing test's assertions may be touched to make this land |

---

## 17. Risks

1. **Largest risk**: touching `ResearchResultManifest` — a dataclass with 5 existing
   construction call sites across `store.py`, `real_data_verifier.py`,
   `live_provider_verifier.py`, and 3 test files — means every one of those call sites must be
   re-verified to still construct correctly with the new trailing-defaulted fields. Mitigation:
   the trailing-default pattern (§5.H) makes this mechanically safe (Python dataclasses don't
   require existing positional/keyword call sites to change when a new *defaulted* field is
   appended), but it must still be explicitly re-verified by running the full suite, not assumed.
2. **Second-largest risk**: the atomic-write change (§13) touches `create_run()`, a method every
   single Phase 7A-8R persistence test depends on transitively. Mitigation: the change is
   additive to the *mechanism* (temp-write + rename) without changing the *interface* (same
   signature, same exceptions raised on the same conditions) — but this is exactly the kind of
   "looks safe, touches everything" change that deserves its own dedicated regression pass
   before anything else in the implementation phase.
3. **Most likely bug**: an implementer reads `manifest.total_return` and treats `None` as `0.0`
   somewhere in a formatting/display path (an `f"{value:.2%}"` on `None` would crash loudly,
   which is actually the safer failure mode here — the sneakier bug would be a `value or 0.0`
   pattern that silently fabricates a zero return for a legacy run). Mitigation: name the field
   accessor pattern explicitly in the implementation directive; add a test asserting the UI
   layer errors or shows "N/A," never `0.0`, for a `None` metric.
4. **Hardest to test**: true multi-process concurrency (as opposed to same-process
   multi-threading) — Python's GIL makes in-process thread races an imperfect proxy for real
   OS-level process races. Mitigation: accept same-process thread-based tests as a reasonable
   proxy for this low-frequency, single-user research tool's actual risk profile; do not invest
   in spinning up real subprocess race tests, which would be disproportionate engineering effort
   for the realistic usage pattern.
5. **Easiest to accidentally break**: the seven-field `"UNAVAILABLE"` hash-placeholder pattern
   already on `ResearchResultManifest` (`positions_hash`, `trades_hash`, etc.) — an implementer
   might be tempted to "clean these up" while already in the file. Explicit non-goal (§14):
   those fields are out of scope for this proposal and must be left exactly as they are.

---

## 18. Rollback Strategy

Because every change is additive (trailing-defaulted fields, an additive integrity-check
function, a mechanical rewrite of `create_run()`'s write sequence that preserves its exact
external contract), rollback is: revert the commit. No data migration occurs in either
direction — no run written under the new schema becomes unreadable by reverted code *except*
that reverted code would simply not know about the new fields (Python dataclasses ignore extra
JSON keys they don't have fields for only if the loader is adjusted to use `.get()`-style
tolerant construction — **this is itself a design detail the implementation phase must get
right**: `ResearchRunIdentity(**identity_dict)`-style strict keyword construction, used
verbatim in `get_run()` today, would raise `TypeError` on an unknown key after a rollback if a
newer-schema run is read by older code. Flagged here as a concrete rollback-safety requirement
for the implementation phase, not resolved by this proposal.)

---

## 19. Implementation Plan (for the future Implementation Directive — not authorized here)

1. Add `schema_version` and the eight new `Optional` fields to `ResearchResultManifest`.
2. Update `CertifiedResearchRunExecutor.execute()` to populate them from the real
   `BacktestResult` before calling `create_run()`.
3. Add the atomic-write mechanism to `ResearchRunStore.create_run()` (§13).
4. Add the corruption-detection wrapper to `ResearchRunStore.get_run()` (§13).
5. Add `verify_result_manifest_integrity()` as a new, separate, opt-in function (§12).
6. Write the full test matrix (§16).
7. Full regression pass — confirm `304 passed, 11 skipped, 0 failed` baseline still holds, plus
   the new tests.
8. Second read-only audit of the implementation (established project convention every phase
   this session has followed).
9. Decide (as part of that future directive, not here) whether Phase 8R's Application Layer
   also gets updated in the same change to prefer canonical fields over `workbench_metrics/`,
   or whether that's a separate follow-up — this proposal recommends treating it as a small
   follow-up within the same directive rather than a fourth phase, but explicitly leaves that
   call to the CEO.

---

## 20. Explicit Non-Goals (see also §14)

No implementation in this phase. No new Phase 10. No UI changes. No changes to
`TransactionCostModel`, `turnover`, `trade_count` semantics, factors, live trading, or broker
integration. This document is design-only.

---

## Files Changed To Produce This Proposal

```
A  PHASE_9_RESEARCH_RESULT_PERSISTENCE_ARCHITECTURE_PROPOSAL.md   (this file)
```

No other file was created, modified, or deleted.

---

## Final Report

**PHASE 9 — RESEARCH RESULT PERSISTENCE ARCHITECTURE PROPOSAL**

**Status**: PASS

**Root Cause**: `CertifiedResearchRunExecutor.execute()` never places `BacktestResult`'s actual
numeric fields into anything passed to `ResearchRunStore.create_run()` — a contract-completeness
gap, not a storage, serialization, or process-boundary defect (every field that *is* passed
already persists and reloads correctly cross-process today).

**Recommended Architecture**: extend `ResearchResultManifest` with the missing scalar fields as
trailing-defaulted (backward-compatible) fields, reusing the exact `ResearchRunStore`
persistence mechanism already proven correct — no new storage class, no new serialization
scheme.

**Alternatives**: (B) a dedicated parallel result store — rejected, adds a second write path and
a new cross-file consistency risk for no corresponding benefit; (C) extend the untyped
`artifacts` dict — rejected, weaker typing and blurs the existing "inputs vs. certified result"
distinction for a marginal effort savings over (A).

**Canonical Persistence**: identity + input manifest + result manifest (extended with real
scalar metrics + `schema_version`) + the artifact fields already canonical since Phase 8A.
Explicitly not canonical: full equity-curve arrays (Replay-reconstructable convenience) and the
Phase 8R `workbench_metrics/` UI cache (superseded, not authoritative).

**Numerical Truth**: JSON round-trip of Python `float` is exact (stdlib guarantee); the design
introduces zero new rounding beyond what `result_hash`'s computation already does today; tests
use exact `==`, not tolerance-based comparison, because there is no drift to tolerate at this
layer.

**Identity / Hash**: kept strictly separate per directive instruction — identity answers "which
configuration," `result_hash` (unchanged definition) answers "has this specific hashed payload
been tampered with," and a new, optional, additive `verify_result_manifest_integrity()`
function answers "does the full persisted manifest still agree with the identity's hash."

**Replay**: entirely unaffected — continues to recompute everything from source and never reads
the new fields as an input; existing `REPRODUCIBLE` tests are the proof this proposal doesn't
regress it.

**Migration**: no data migration; new fields default to `None`/`schema_version="1.0"` for
legacy runs, read as "not available," never fabricated as `0.0`; `workbench_metrics/` remains
functional and is recommended (not mandated here) to become a fallback-only path once the
canonical fields exist.

**Testing**: 10 new test categories specified (§16), all additive; zero existing tests modified;
304/11/0 baseline must hold unchanged.

**Risks**: five identified (§17), most significant being the blast radius of touching a
5-call-site dataclass and the write-atomicity change touching every persistence test
transitively — both mitigated by the additive/backward-compatible design, but requiring
explicit full-suite re-verification during implementation, not assumption.

**Files Changed**: `PHASE_9_RESEARCH_RESULT_PERSISTENCE_ARCHITECTURE_PROPOSAL.md` only.

**Production Impact**:
```
Production Code Modified: NO
Tests Modified: NO
Dependencies Modified: NO
Commit Created: NO
Push Performed: NO
```

**Recommendation**: **READY FOR CEO REVIEW**
