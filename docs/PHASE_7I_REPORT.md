# 🏛️ Phase 7I Executive Report
**Corporate Action Integration & Persistent Dataset Certification**
**Directive ID**: CEO-2026-08-03-REBUILD-007I
**Target Repository**: `/Users/yuhanluo/ashare-quant`
**Git Branch**: `main`
**Base Commit**: `22f19ab` (Phase 7H). **This commit**: uncommitted at time of writing — update this line with the real hash once committed, per the project's existing convention of never fabricating a commit hash for work not yet committed.

---

## 1. Executive Verdict

**PASS WITH LIMITATIONS**

All four objectives (A–D) are implemented, adversarially tested, and independently re-audited via direct code inspection (not test-output alone). Two residual limitations keep this from an unqualified PASS — both disclosed in full in Section 9, neither hidden or minimized.

---

## 2. Findings Addressed

| Finding | Status |
|---|---|
| F7I-01 — Corporate actions not consumed by backtest path | **CLOSED**: `CorporateActionAdjuster` + `PITGate.filter_pit_corporate_actions` now produce a PIT-correct adjusted price series that, adversarially proven, changes `BacktestEngine`'s actual output (see §5, TEST G) |
| F7I-02 — Dataset manifests bind to in-memory data, not a persisted artifact | **CLOSED (mechanism)**: `PersistentDatasetManifestManager` hashes real on-disk Parquet bytes; `PersistentDatasetLock` fails closed on missing/corrupted/tampered artifacts. See §9 for what remains open. |
| F7I-03 — Two competing canonical serialization implementations | **CLOSED**: `manifest.py` now delegates to `canonical.py`; one implementation, one contract, tested to agree |
| F7I-04 — Empty secret-audit scan reported as `PASSED` | **CLOSED**: now returns `NO_TARGET_FILES`, distinct from `PASSED` |

Two additional bugs were found and fixed while implementing the above (not in the original audit, discovered during Phase 7I's own code inspection):

- **`dataset_lock.py` version-check bypass**: `DatasetVersionLock.lock` skipped its mismatch check whenever `dataset_version == "ds_v1.0"` exactly — a hardcoded backdoor that violated the directive's own "different content, same version string must not be accepted" requirement. Removed; no existing test relied on it.
- **Secret-audit suppression scope bug**: the "unavailable"/"none" false-positive suppression checked the *whole file*, not the text near the match — meaning a genuine leaked token could be hidden by the unrelated presence of the word "unavailable" anywhere else in the same document. Scoped to a local context window; regression test added (`test_unavailable_elsewhere_in_file_does_not_mask_a_real_leak_nearby`).

---

## 3. Architecture Changes

- `CorporateActionContract` gained mandatory `available_at`/`received_at` fields — PIT visibility is no longer inferable/optional for corporate actions.
- New store (`CorporateActionStore`) and adjuster (`CorporateActionAdjuster`) modules — additive, do not modify `BacktestEngine`, `SnapshotManager`, `RevisionStore`, or any Phase 7A–7H PIT/replay/immutability code.
- New persistent-manifest layer (`persistent_manifest.py`, `persistent_dataset_lock.py`) — additive, sits alongside (does not replace) the existing snapshot-based `DatasetVersionLock`.
- `canonical.py` rewritten internally (recursive pre-canonicalization instead of relying on `json.dumps(default=...)`) but its public API (`to_canonical_json`, `compute_canonical_sha256`) is unchanged — no caller needed to change its call signature.
- `secret_audit.py`'s return schema gained a new possible `status` value (`NO_TARGET_FILES`); existing `PASSED`/`FAILED_LEAK_DETECTED` callers are unaffected since they only match on those exact strings.

---

## 4. Files Changed

**New files (8):**
`src/data/revision/corporate_action_store.py`, `src/quant/adjustment/corporate_action_adjuster.py`, `src/quant/adjustment/__init__.py`, `src/data/domain/persistent_manifest.py`, `src/quant/reproducibility/persistent_dataset_lock.py`, `tests/test_corporate_action_integration.py`, `tests/test_persistent_dataset_certification.py`, `tests/test_canonical_serialization_unification.py`, `tests/test_secret_audit_hardening.py`, plus this spec/report pair.

**Modified files (11):**
`src/data/contracts/corporate_action.py`, `src/data/providers/tushare_provider.py`, `src/data/providers/akshare_provider.py`, `src/data/validation/pit_gate.py`, `src/data/domain/manifest.py`, `src/quant/reproducibility/canonical.py`, `src/quant/reproducibility/dataset_lock.py`, `src/data/security/secret_audit.py`, `tests/test_data_contracts.py`, `tests/test_historical_corporate_actions.py`, `docs/PHASE_7H_REPORT.md` (unrelated pre-existing edit from the prior session, carried over).

No file under Phase 7A–7H's PIT/snapshot/revision/replay/immutability core (`revision_store.py`, `snapshot_manager.py`, `pit_gate.py`'s existing methods, `store.py`'s immutability check, `replay_engine.py`'s fail-closed logic) was modified in a way that changes its existing behavior — `pit_gate.py` only gained a new method, existing methods untouched.

---

## 5. Tests Added — Mapped to Directive Requirements

| Directive test | File | Result |
|---|---|---|
| A (split discontinuity) | `test_corporate_action_integration.py::test_split_unadjusted_shows_discontinuity_adjusted_does_not` | PASS |
| B (cash dividend) | `::test_cash_dividend_applies_ex_dividend_adjustment`, `::test_dividend_gte_reference_price_fails_closed` | PASS |
| C (available_at > as_of excluded) | `::test_action_not_yet_available_is_excluded_from_snapshot` | PASS |
| D (effective_date<=as_of, available_at>as_of excluded) | `::test_effective_date_before_as_of_but_available_at_after_is_excluded` | PASS |
| E (revision immutability) | `::test_corporate_action_revision_immutability_and_pit_correctness` | PASS |
| F (determinism) | `::test_same_corporate_action_adjusted_backtest_is_deterministic` | PASS |
| G (measurable consumption proof) | `::test_backtest_result_measurably_changes_from_corporate_action_consumption` | PASS |
| Persistence 1–7 | `test_persistent_dataset_certification.py` (9 tests, incl. 2 extra: uncertified-dataset rejection, empty-directory rejection) | PASS |
| Canonical hash golden tests | `test_canonical_serialization_unification.py` (12 tests) | PASS |
| Secret audit hardening | `test_secret_audit_hardening.py` (8 tests) | PASS |

**37 new tests, all passing. Zero tests deleted or weakened to make a number look better.**

---

## 6. Full Test Result

```
PYTHONPATH=. ./venv/bin/pytest
Before Phase 7I: 164 passed, 11 skipped, 0 failed
After Phase 7I:  201 passed, 11 skipped, 0 failed
```

11 skips unchanged, all still `LIVE_PROVIDER_CREDENTIALS_UNAVAILABLE` / `REAL_DATA_CREDENTIALS_UNAVAILABLE` — `TUSHARE_TOKEN` remains unset in this environment. No skip was converted to a pass by weakening its condition.

---

## 7. Verification Matrix

| Area | Status | Evidence |
|---|---|---|
| Corporate action PIT filtering | **VERIFIED** | `PITGate.filter_pit_corporate_actions`; TEST C/D |
| Corporate action adjustment math (split/bonus/dividend) | **VERIFIED** | TEST A/B; fails closed on invalid ratios or dividend ≥ reference price |
| Corporate action revision immutability | **VERIFIED** | TEST E; `CorporateActionStore` append-only |
| Backtest measurably consumes corp-action data | **VERIFIED** | TEST G — raw vs adjusted runs diverge, adjusted removes the fabricated drawdown |
| Corp-action adjustment wired into a mandatory production entry point | **NOT DONE** | See §9 — no such entry point exists anywhere in this codebase yet, for any data type |
| Persistent dataset content hashing | **VERIFIED** | Real file bytes hashed via streaming SHA-256; content-change detected (persistence TEST 2) |
| Persistent dataset lock fail-closed behavior | **VERIFIED** | Missing/corrupted/tampered artifact all raise (persistence TEST 3/4/5) |
| Dataset version identity uniqueness | **VERIFIED** | Persistence TEST 7 + `dataset_lock.py` backdoor fix |
| Real dataset persisted into the actual repo | **NOT DONE** | See §9 |
| Canonical serialization — single authority | **VERIFIED** | `manifest.py` delegates to `canonical.py`; tested to produce identical hashes |
| Canonical float determinism | **VERIFIED (fixed a real bug)** | `0.1+0.2` now hashes identically to `0.3`; previously did not |
| Secret audit empty-scan distinction | **VERIFIED** | `NO_TARGET_FILES` distinct from `PASSED` |
| Secret audit local-context suppression | **VERIFIED (fixed a real bug)** | Regression test proves a distant "unavailable" no longer masks a real leak |
| Existing PIT/revision/snapshot/replay/immutability protections | **VERIFIED unchanged** | Full existing suite still green; no existing test modified except two `CorporateActionContract` fixture constructions updated for the new required fields |
| Live-provider network verification | **NOT VERIFIED (unchanged from 7G/7H)** | `TUSHARE_TOKEN` unavailable |

---

## 8. Security Impact

- `dataset_lock.py` backdoor removed (see §2).
- `secret_audit.py` false-negative window closed (see §2).
- No secrets were fetched, printed, logged, or committed in this session. `SecurityAuditManager.audit_directory_for_secrets` was itself audited and hardened, not merely invoked.

## 9. Remaining Limitations (Not Fabricated as Closed)

1. **No mandatory enforcement point.** `CorporateActionAdjuster` and `PersistentDatasetLock` are correct, adversarially tested, additive primitives — but nothing in this codebase *forces* a caller to use them. A caller can still construct `BacktestEngine.run_backtest(daily_prices=raw_unadjusted_prices, ...)` directly and get a "plausible-looking but historically incorrect" result, because **no single mandatory production orchestrator exists anywhere in this codebase** connecting raw provider data → PIT gating → corporate-action adjustment → persistent dataset → backtest. This is not a regression introduced by Phase 7I — the same characteristic was already true of PIT gating itself before this phase (`PITGate` is correct and tested, but a caller could bypass `HistoricalDataWarehouse` and read raw revisions directly). Phase 7I closes the *capability* gap the audit found; it does not — because none of Phase 7 ever has — close the *"nothing can misuse this from arbitrary code"* gap. Answering directive §15's adversarial question precisely: **the specific mechanism gap identified by the audit (corporate actions silently ignored, dataset identity unbound to any real file) is closed and proven correct; whether an actual future orchestrator built on top of these primitives uses them correctly is a property of that not-yet-written orchestrator, not of Phase 7I.**
2. **`data/research/` in the real repository is still empty.** All persistence golden tests use real Parquet files and real byte-level hashing, but via `tmp_path` (cleaned up after each test run) rather than a permanently committed dataset. The F6 finding ("no dataset ever persisted to the real repo path") is mechanically provably *closeable* now, but not closed as a fact about the current repository state. Committing a permanent fixture dataset was not done without being asked — this is a decision for the project owner, not a unilateral call.
3. **`LiveTuShareAdapter`'s corporate-action field mapping remains unverified against a live response** (unchanged from Phase 7H — no `tushare` package installed, no token).
4. **Live-provider network verification remains `NOT VERIFIED`** (unchanged from 7G/7H) — `TUSHARE_TOKEN` unavailable in this environment.

---

## 10. Anti-Fabrication Statement

- No real network call was made in this session.
- No claim is made that real market data has been ingested or persisted into the repository.
- Every "VERIFIED" tag in §7 is backed by a cited, currently-passing adversarial test re-run in this session, plus direct code re-reading (not test-output trust alone) during the mandatory second audit.
- The two bugs found during implementation (§2) are disclosed as bugs found and fixed, not presented as if they were designed correctly from the start.
- Section 9's limitations are stated as plainly as the successes in Section 7 — nothing is softened.

---

## 11. Final Verification Matrix Summary

**PASS WITH LIMITATIONS — CORPORATE-ACTION AND PERSISTENT-DATASET MECHANISMS BUILT, ADVERSARIALLY VERIFIED, AND CODE-AUDITED; NO PRODUCTION ORCHESTRATOR EXISTS TO ENFORCE THEIR USE, AND NO DATASET IS YET PERSISTED IN THE REAL REPOSITORY. LIVE-PROVIDER VERIFICATION REMAINS UNCHANGED FROM PHASE 7G/7H.**

---

🛑 **STOP CONDITION**

Phase 7I (Objectives A, B, C, D) is complete, tested, and code-audited, but the working tree is uncommitted pending CEO review.

- No Phase 8 work has started.
- No broker integration, live trading, automatic execution, or real-money functionality was added.
- No live credentials were fabricated.

System is **STOPPED and WAITING FOR CEO REVIEW** — specifically: (1) whether to commit the current changes, and (2) whether the two disclosed residual limitations (no mandatory orchestrator; no dataset actually persisted in the repo) warrant a further hardening phase before Phase 7 is considered finally accepted, per directive §21.
