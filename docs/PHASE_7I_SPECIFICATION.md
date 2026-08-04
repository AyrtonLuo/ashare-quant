# Phase 7I — Corporate Action Integration & Persistent Dataset Certification Specification

**Directive ID**: CEO-2026-08-03-REBUILD-007I
**Status**: IMPLEMENTED (this document written concurrently with the work, per project convention of pairing a spec with its report)
**Precondition**: Phase 7H (`22f19ab`) — anti-fabrication closure of the live-provider certification pipeline. Not modified by this phase.
**Trigger**: CEO directive 007I, itself triggered by a read-only Phase 7 architecture audit that found two genuine architecture-level gaps: (1) corporate actions were never consumed by the backtest path, and (2) dataset manifests/hashes/locks bound to in-memory data, never a real persisted artifact.

---

## 1. Objective

Four objectives, unchanged from the directive:

- **A** — Make corporate actions part of the actual historical backtest computation, PIT-correct, with explicit RAW vs ADJUSTED semantics.
- **B** — Make dataset identity bind to a real, on-disk, checksummed persistent artifact.
- **C** — Establish one authoritative canonical serialization/hash implementation.
- **D** — Make secret auditing fail closed (distinct status) when there is nothing meaningful to scan.

---

## 2. Objective A — Corporate Action Integration

### Design decision
`BacktestEngine` (`src/quant/backtest/engine.py`) remains a pure numeric simulator over `Dict[str, List[float]]` — it does not import or know about corporate actions. This matches the existing architecture: PIT/snapshot gating is likewise done by callers (`HistoricalDataWarehouse`, `PITGate`) before data ever reaches the engine, not inside the engine itself. Corporate-action adjustment follows the same pattern: it happens in a new, dedicated, independently-testable layer, and the engine consumes whatever series it is given.

### What was built
- `src/data/contracts/corporate_action.py` — added `available_at: datetime` and `received_at: datetime` fields (required, no default) to `CorporateActionContract`. An action's PIT visibility is now a first-class, mandatory concept, never inferred from `ex_date`/`announcement_date`.
- `src/data/validation/pit_gate.py` — added `PITGate.filter_pit_corporate_actions(actions, as_of_cutoff)`, symmetric with the existing `filter_pit_contracts`.
- `src/data/revision/corporate_action_store.py` (new) — `CorporateActionStore`, mirroring `RevisionStore`'s append-only, never-mutate, PIT-query-returns-latest-visible semantics, keyed by `(symbol, ex_date, action_type)`.
- `src/quant/adjustment/corporate_action_adjuster.py` (new) — `CorporateActionAdjuster.adjust(dates, raw_prices, actions, as_of)`. Backward-adjustment: `STOCK_SPLIT` and `BONUS_ISSUE` divide pre-event prices by `(1 + ratio)`/`split_ratio`; `CASH_DIVIDEND` multiplies pre-event prices by `(ref_price - dividend) / ref_price` using the raw post-event price as reference. `RIGHTS_OFFERING` and any unknown `action_type` raise (`FAIL CLOSED`) rather than guess a formula. All actions are first filtered through `PITGate.filter_pit_corporate_actions` — an action not yet `available_at <= as_of` cannot affect the series regardless of its `ex_date`. Returns `AdjustedPriceSeries` with `raw_prices` and `adjusted_prices` as distinct fields — never conflated.

### Construction sites updated
`tushare_provider.py` (both the synthetic fixture and the live-network adapter), `akshare_provider.py`, and the two pre-existing tests that construct `CorporateActionContract` directly. The live adapter (`LiveTuShareAdapter.fetch_corporate_actions`) derives `available_at` from the provider's real `ann_date` field and fails closed (`ProviderError`) if `ann_date` is absent, rather than falling back to `ex_date` (which the directive explicitly prohibits).

### Incidental fix
`tests/test_historical_corporate_actions.py` used `action_type="SPLIT"`, which does not match the contract's own documented vocabulary (`"STOCK_SPLIT"`) and would not have been recognized by the new adjuster. Corrected to `"STOCK_SPLIT"`.

---

## 3. Objective B — Persistent Dataset Certification

### Design decision
Build on the existing `ParquetStorageAdapter` (Parquet under `data/research/`) rather than introducing a second storage architecture, per directive scope control. Add a manifest layer that hashes real file bytes, and a lock that binds a research run to that hash.

### What was built
- `src/data/domain/persistent_manifest.py` (new) — `PersistentDatasetManifestManager.build_manifest(dataset_id, dataset_version, directory, created_at)` reads every `*.parquet` file in `directory` (sorted for determinism), computes a streaming SHA-256 of each file's actual bytes, and folds them into one `content_sha256` for the directory. Also records `file_size`, `row_count`, `schema_hash` (fails closed on schema mismatch across files), `min/max_trading_date`, and `universe_hash` (from the sorted symbol set). Fails closed (`FileNotFoundError`) if the directory is missing or empty; fails closed (`ValueError`) if a file cannot be read (corruption).
- `PersistentDatasetManifestStore` — immutable registry: once `(dataset_id, dataset_version)` is certified with a content hash, certifying different content under the same version string raises `FAIL CLOSED`. Re-certifying identical content is a no-op.
- `src/quant/reproducibility/persistent_dataset_lock.py` (new) — `PersistentDatasetLock.lock(dataset_id, dataset_version, directory, manifest_store)`: fails closed if uncertified, if the artifact directory/files are missing, or if the recomputed content hash no longer matches the certified one (tamper/corruption after certification).

### Incidental fix (found while implementing this objective)
`src/quant/reproducibility/dataset_lock.py` (the pre-existing `DatasetVersionLock`, unrelated to the new persistent lock) contained: `if snapshot.dataset_version != dataset_version and dataset_version != "ds_v1.0":` — a hardcoded exemption that skipped the version-mismatch check entirely whenever the caller passed exactly the string `"ds_v1.0"`. This directly violated the "different content, same dataset_version string must not be accepted" requirement (directive §9, TEST 7) at the existing snapshot-lock layer. No existing test relied on the exemption (the one test exercising mismatch used `"ds_NON_EXISTENT"`). Removed.

### What was deliberately not done
No dataset was persisted into the repository's real `data/research/` directory. The golden tests exercise real file I/O via `pytest`'s `tmp_path` (genuine Parquet files, genuine byte-level hashing, genuinely deleted/corrupted/tampered in the test) — this proves the *mechanism* is real, not mocked. But it means `data/research/` in the actual repository remains empty after this phase; the F6 finding ("no dataset ever persisted to the real repo path") is not closed by this phase, only the *capability* to do so correctly is. Committing a permanent `GOLDEN_DATASET` Parquet fixture into the repo was considered out of scope for this directive and was not done without being asked.

---

## 4. Objective C — Canonical Serialization Unification

### Root cause found
`canonical.py`'s `_canonicalize` float-rounding branch (`isinstance(obj, float): return round(obj, 6)`) was **dead code** for ordinary Python floats: `json.dumps`'s `default=` callback is only invoked for types the encoder doesn't recognize natively, and `float` is natively recognized — so the documented "deterministic float rounding to 6 decimal places" never actually ran. `0.1 + 0.2` serialized as `0.30000000000000004`, not `0.3`. Verified empirically before fixing.

### What was built
Rewrote `canonical.py` to recursively pre-canonicalize the entire structure into plain JSON-safe values *before* calling `json.dumps` (no longer relying on `default=`), so every float anywhere in a nested structure is actually rounded. Explicit handling added for: `dict`, `list`/`tuple` (order preserved), `str`, `bool`, `int`, `float` (rounded to 6dp; NaN/Infinity rejected via `ValueError`, and `json.dumps(..., allow_nan=False)` as a second guard), `None`, `datetime`, `date`, `Decimal` (exact string, never coerced through float), `Enum` (`.value`), `numpy` scalars (`.item()`), dataclasses, and objects exposing `to_dict()`. Anything else now raises `TypeError` — the old silent `str(obj)` fallback for unrecognized types is removed.

`src/data/domain/manifest.py`'s `DatasetManifestManager.compute_sha256` — previously its own independent `json.dumps(data_payload, sort_keys=True)` with no float/datetime handling at all — now delegates directly to `compute_canonical_sha256`. There is exactly one hash implementation in the codebase.

---

## 5. Objective D — Secret Audit Hardening

### Root causes found
1. `SecurityAuditManager.audit_directory_for_secrets` returned `{"status": "PASSED", ...}` whenever the target directory was missing *or* contained zero auditable files — indistinguishable from a genuine clean scan.
2. A more serious latent bug found while reading the function to fix (1): the "this looks like a placeholder, not a real secret" suppression (`"unavailable" not in content and "none" not in content`) checked those words against the **entire file's content**, not the text near the matched pattern. A file containing the word "unavailable" *anywhere* — even in a completely unrelated field — would suppress every suspicious-pattern match in that file, including a genuine leaked token elsewhere in the same document.

### What was fixed
- Missing directory or zero scannable files now returns `status: "NO_TARGET_FILES"`, `security_certification: "AUDIT_NOT_MEANINGFUL_..."` — never `PASSED`.
- The suppression check is now scoped to a small window (±40 chars) around each individual match, not the whole file.

---

## 6. Non-Goals (unchanged from directive)

- No broker/execution/live-trading functionality.
- No Phase 8 work of any kind.
- No fabricated live-provider data; `TUSHARE_TOKEN` remains unavailable in this environment and live-provider tests remain honestly `SKIPPED`.
- No rewrite of the storage architecture; built on the existing `ParquetStorageAdapter`.

## 7. Acceptance / Stop Condition

Phase 7I closes when all 21 checkboxes in directive §19 are true and the CTO's second read-only audit (directive §18) confirms the code matches the tests. See `PHASE_7I_REPORT.md` for the verification matrix and the honest answer to the required adversarial question (directive §15).
