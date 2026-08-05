# 🏛️ Phase 9 Executive Report
**Research Result Persistence Hardening**
**Target Repository**: `/Users/yuhanluo/ashare-quant`
**Git Branch**: `main`
**Base Commit**: `29372bf` (Phase 8R + Phase 2 context hardening). **This commit**: pending (local, not pushed).

---

## 1. Executive Summary

`PHASE_9_RESEARCH_RESULT_PERSISTENCE_ARCHITECTURE_PROPOSAL.md` established that
`CertifiedResearchRunExecutor.execute()` never placed `BacktestResult`'s real numeric fields
(`total_return`, `sharpe_ratio`, `max_drawdown`, etc.) into anything handed to
`ResearchRunStore.create_run()` — `ResearchResultManifest` carried only hashes, seven of them
permanently `"UNAVAILABLE"` since Phase 7B. This was classified a **contract-completeness gap**,
not a storage/serialization/process-boundary defect: every field that *was* written already
round-tripped correctly cross-process.

This phase implements the proposal's recommended **Option A** exactly as specified: extend
`ResearchResultManifest` with eight trailing-defaulted `Optional` scalar fields plus
`schema_version`, populate them in `CertifiedResearchRunExecutor.execute()`, and close two
pre-existing gaps discovered during design (non-atomic writes, opaque corruption errors) in the
same pass since both live in the exact code path already being touched. `result_hash`'s
definition and computation point are unchanged. Replay is unaffected — verified both by the
existing `REPRODUCIBLE` suite passing unmodified and by a new static-source test asserting
`CertifiedReplayEngine.replay` never reads the new fields as an input.

**Verdict: PASS.** Full regression suite: **319 passed, 11 skipped, 0 failed** (up from the
304/11/0 Phase 8R baseline — 15 new Phase 9 tests, zero existing tests modified). No file outside
the four scoped in the proposal was touched.

---

## 2. Files Changed

**Modified (4, exactly the set the proposal scoped in §5.H / comparison matrix):**
`src/quant/reproducibility/manifest.py` (`schema_version` + 8 trailing-defaulted `Optional`
fields on `ResearchResultManifest`), `src/quant/reproducibility/identity.py`
(`verify_result_manifest_integrity()`, new opt-in function), `src/quant/reproducibility/store.py`
(atomic temp-dir + `os.rename` write in `create_run()`; `_load_json()` corruption wrapper in
`get_run()`), `src/quant/research/integrity_gate.py` (`execute()` now populates the 8 new fields
from the real `BacktestResult` it already holds).

**New (2):** `tests/test_phase9_research_result_persistence.py` (15 tests across the 9 categories
specified in the proposal's §16 testing matrix), this report.

**Not modified:** `src/quant/backtest/engine.py`, `FactorRegistry`, `PortfolioConstructor`,
any PIT/snapshot/revision/corporate-action/canonical-hash logic, `CertifiedReplayEngine`, the
Phase 8R Application Layer (`src/app/research_application.py`) — see §6.

---

## 3. Implementation vs. Proposal

Matches `PHASE_9_..._PROPOSAL.md` §19 steps 1–7 exactly:

1. `schema_version: str = "1.0"` + 8 `Optional` fields added to `ResearchResultManifest`
   (`manifest.py`) — trailing-defaulted, so all 5 existing construction call sites (`store.py`,
   `real_data_verifier.py`, `live_provider_verifier.py`, and 3 test files) remain valid
   unmodified. Confirmed by grep (§4 below) and by the full suite passing unchanged.
2. `CertifiedResearchRunExecutor.execute()` (`integrity_gate.py`) now passes
   `schema_version="2.0"` and all 8 real `backtest_result.*` values into the
   `ResearchResultManifest` it already constructs — `result_hash`'s own computation, three lines
   above, is untouched.
3. Atomic write (`store.py::create_run`): each attempt writes to a uniquely-named
   `<run_path>.tmp-<uuid4>` directory, then `os.rename()`s it into place. A failure mid-write
   leaves only an orphaned temp directory, never a partial run visible under the real `run_id`.
   The per-attempt-unique temp name also makes same-`run_id` races safe: each writer builds its
   own temp directory independently; exactly one `os.rename` to the shared final path can win,
   the other's `except` branch detects the now-existing `run_path` and re-raises the pre-existing
   immutability `ValueError`.
4. Corruption detection (`store.py::get_run` → `_load_json`): a `json.JSONDecodeError` on any of
   the four persisted files now raises `RuntimeError("FAIL CLOSED: corrupted persisted file for
   run '<id>': <path>")` instead of an opaque decode error surfacing from inside `get_run()`.
5. `verify_result_manifest_integrity(identity, result_manifest)` (`identity.py`) — recomputes
   `compute_canonical_sha256({"sharpe","return","mdd"})` from the manifest's own stored scalars
   and compares against `identity.result_hash`. Opt-in only, never called inside `get_run()`
   itself (per proposal §12 — making it mandatory would be an unauthorized behavior change to an
   existing, widely-used method). Returns `False` (never raises) for a `schema_version == "1.0"`
   legacy manifest, which has no scalars to check against — an honest "not available," not a
   tamper signal.
6. Full test matrix written (`tests/test_phase9_research_result_persistence.py`, 15 tests,
   9 categories per §16): serialization round-trip, numerical-truth (including the disclosed
   6-decimal ceiling, §11 below), identity/hash stability, cross-process reload, replay
   non-interference (both behavioral and static-source), corruption fail-closed, legacy
   (`schema_version` absent) compatibility, and a 5-thread same-`run_id` concurrency race.
7. Full regression pass: **319 passed, 11 skipped, 0 failed.**

---

## 4. Verification (re-read, not test-trust alone)

- **Backward compatibility**: `grep -rn "ResearchResultManifest(" src/ tests/` confirms all 5
  pre-existing call sites (`store.py:111` — the `get_run()` reconstruction itself — plus
  `integrity_gate.py`, `real_data_verifier.py`, `live_provider_verifier.py`, and 3 test files)
  still construct successfully with only their original positional/keyword arguments; the new
  fields are never required.
- **`result_hash` untouched**: `integrity_gate.py`'s `result_hash = compute_canonical_sha256(...)`
  call is unchanged and appears above the `ResearchResultManifest(...)` construction it feeds —
  the 8 new fields are populated *after* the hash is already computed, from the same
  already-in-scope `backtest_result` object, never participating in the hash payload.
  `test_identity_result_hash_definition_is_unchanged` asserts this behaviorally against a real
  certified run.
- **Replay non-interference**: verified two ways — the existing `REPRODUCIBLE`-status replay
  tests pass unmodified, and a new static test
  (`test_replay_source_never_references_result_manifest_scalar_fields`) inspects
  `CertifiedReplayEngine.replay`'s actual source via `inspect.getsource` and asserts none of
  `result_manifest.total_return` / `.sharpe_ratio` / `.max_drawdown` appear in it — Replay always
  recomputes from source and compares only the hash, exactly as before.
- **No circular import**: `identity.py` now imports `compute_canonical_sha256` from
  `canonical.py`; `canonical.py` does not import `identity.py` — confirmed by the full suite
  importing and collecting cleanly (no `ImportError` at collection time).
- **Scope**: `git diff --stat` against the pre-Phase-9 baseline shows exactly the 4 files listed
  in §2, matching the proposal's own comparison matrix ("Phase 8A files touched:
  `manifest.py`, `integrity_gate.py`" plus the 2 files — `identity.py`, `store.py` — the
  proposal's own §13 atomicity/integrity section separately scoped in).

---

## 5. Numerical Truth — Corrected Finding, Disclosed Not Hidden

The proposal's §11 originally claimed the new fields preserve "full IEEE-754 double precision...
no additional rounding introduced." Implementation-time verification found this **inaccurate**:
`ResearchRunStore.create_run()` writes the *entire* manifest through `to_canonical_json`, which —
a pre-existing, project-wide behavior since Phase 7I, not introduced by this phase — rounds every
float to 6 decimal places, not only the small `result_hash` payload. In practice this is harmless:
`BacktestEngine` already rounds every scalar to 4 decimals before `BacktestResult` is constructed,
and a 4-decimal value is exactly representable at 6-decimal precision. Corrected policy: persisted
values are exact up to the existing 6-decimal canonicalization ceiling, not unlimited.

Both the realistic case (4-decimal values, bit-identical round-trip) and the edge case
(`1/3`, which does lose precision at the 6-decimal ceiling) are now separately tested and asserted
— `test_numerical_truth_real_backtest_precision_survives_disk_round_trip` and
`test_numerical_truth_documents_existing_six_decimal_canonicalization_ceiling` — so the ceiling is
a documented, tested fact rather than a silent gap.

---

## 6. Explicitly Deferred (per proposal §9 item 9 / §15 — not decided in this phase)

The proposal's own implementation plan (§19 step 9) identified a follow-up decision and
explicitly left it to CEO review rather than resolving it here: whether the Phase 8R Application
Layer (`src/app/research_application.py::get_research_run`) should be updated in this same
directive to read the new canonical `result_manifest` fields (falling back to the
`workbench_metrics/` side cache only for legacy `schema_version == "1.0"` runs), or treated as a
separate follow-up. **Not implemented in this phase** — `research_application.py` is unmodified;
`get_research_run()` still reads exclusively from `workbench_metrics/` via `_load_metrics()`,
including its existing `metrics.get(key, 0.0)` fallback pattern for a missing cache file. This is
pre-existing Phase 8R behavior, not a Phase 9 regression, and is called out here rather than
silently left for a future session to rediscover. Recommend a small, separate follow-up directive
to switch `get_research_run()` to prefer the canonical fields (using `None`, never `0.0`, for
genuinely legacy runs) and retire `workbench_metrics/` once that lands.

---

## 7. Limitations Carried Forward (unchanged, already CEO-disclosed)

Same class already disclosed in Phase 8A/8R and untouched by this phase: `BacktestResult.turnover`
is a fixed placeholder, `trade_count` reflects simulated days rather than real trades, and live
provider verification remains unavailable (`TUSHARE_TOKEN` unset — all data `GOLDEN_DATASET`).
This phase persists these fields faithfully; it does not change what they mean.

---

## 8. Test Summary

```
319 passed, 11 skipped, 0 failed
Test Command: PYTHONPATH=. ./venv/bin/pytest
```

15 new tests in `tests/test_phase9_research_result_persistence.py`; zero existing test assertions
modified. The 11 skips are the pre-existing live-provider network tests (`TUSHARE_TOKEN` absent),
unrelated to this phase.

---

## 9. Production Impact

```
Production Code Modified: YES — 4 files, additive/trailing-defaulted only (§2/§3)
Tests Modified: NO (15 new tests added; 0 existing tests changed)
Dependencies Modified: NO
Trading / Broker / Execution Code: NONE
Commit Created: pending this report
Push Performed: NO
```

**Recommendation: READY FOR CEO REVIEW.** Open item for a future directive: §6's Application
Layer follow-up (`research_application.py` canonical-field preference), not authorized or
implemented here.
