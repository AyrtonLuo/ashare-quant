# Phase 7H — Genuine Real-Data Sourcing & Anti-Fabrication Closure Specification

**Directive ID**: CEO-2026-08-03-PHASE-7H
**Status**: PROPOSED (not yet implemented)
**Precondition**: Phase 7G (`d5b6dd3` / `28595ad` / `1d05b93`) — PIT, snapshot, revision, replay, and immutability architecture is CLOSED and considered sound.
**Trigger**: CEO architecture audit of `28595ad` found that every "REAL_PROVIDER" / "LOCAL_PRODUCTION_VERIFICATION_DATA" / "production dataset" claim in Phase 7C–7G is backed by formula-generated numbers, not real or cached-real market data.

---

## 1. Overview & Objective

Phase 7A–7G proved that *if* genuine data enters the platform, it will be handled with correct PIT semantics, immutable revisions, deterministic replay, and fail-closed behavior. That architecture audit is not in question.

What Phase 7H closes is a separate, more basic gap: **no genuine market data has ever entered the platform.** The certification pipeline currently cannot distinguish "a real provider was called and returned this number" from "this number was written as a Python literal." Phase 7H makes that distinction structural and enforced, rather than a matter of report wording.

This phase does **not** touch PIT/snapshot/revision/replay internals. It only touches: (a) how provider adapters obtain values, (b) how `data_origin` is derived, and (c) fail-closed behavior of the two silent-fallback paths found during audit.

---

## 2. Root Cause Findings (evidence from `28595ad`)

| # | Finding | Location |
|---|---|---|
| F1 | `TuShareAdapter.fetch_market_data`/`fetch_fundamental_data`/`fetch_corporate_actions` return hardcoded literals (`1650.00`, `ex_date="2026-06-15"`, ...) — zero network calls. | `src/data/providers/tushare_provider.py` |
| F2 | `AkShareProviderAdapter` — identical pattern, different literal multipliers. | `src/data/providers/akshare_provider.py` |
| F3 | `RealDataVerificationEngine.generate_verification_dataset` generates all 20-symbol/8-date prices via `p_base * (1.0 + 0.01 * (i % 5))`, never reads a file or calls a provider, yet is tagged `provider="tushare_pro_primary"`. | `src/data/warehouse/real_data_verifier.py:87-165` |
| F4 | `is_live_provider_available()` toggles `data_origin` between `REAL_PROVIDER` and `LOCAL_PRODUCTION_VERIFICATION_DATA` **without changing which numbers are used** — the same `base_prices` literal dict feeds both branches. | `src/data/warehouse/live_provider_verifier.py:83-141` |
| F5 | Cross-provider reconciliation reconciles `TuShareAdapter()` against `AkShareProviderAdapter()` — two hardcoded stubs — guaranteeing `MATCH`/`ACCEPTABLE_DIFFERENCE` by construction. | `src/data/warehouse/live_provider_verifier.py:52-73` |
| F6 | No `.parquet` or `.duckdb` file exists anywhere in the repository. `ParquetStorageAdapter`/`DuckDBQueryEngine` point at `data/research/`, which contains no such files. | filesystem check, `src/data/storage/parquet_adapter.py:17`, `duckdb_adapter.py:14` |
| F7 | `warehouse_loader.py` silently substitutes a hardcoded fixture when Parquet lookup is empty, instead of failing closed. | `src/data/warehouse/warehouse_loader.py:46-59` |
| F8 | `replay_engine.py` silently substitutes a hardcoded price series when the run's saved `daily_prices` artifact is missing, instead of failing closed. | `src/quant/reproducibility/replay_engine.py:65-68` |

**Consequence**: if `TUSHARE_TOKEN` is set today, F4 means the platform would begin labeling F1/F3's fabricated numbers as `REAL_PROVIDER` / `VERIFIED_LIVE_PROVIDER` without ever making a data-bearing network call. This is the exact scenario Section 13 of the CEO handover forbids.

---

## 3. Mandatory Closure Requirements

### REQ-1 — `data_origin` must be derived from provenance, not from a credential flag
`REAL_PROVIDER` may only be set on a `TemporalDataContract`/`MarketDataContract` when the value was produced inside a code path that made a real network call and parsed a real response. Add a non-optional `fetched_via_network: bool` (or equivalent provenance marker) set only at the point of the actual HTTP/SDK response parse. `is_live_provider_available()` alone must never be sufficient to set `REAL_PROVIDER`.

### REQ-2 — Real provider adapters
Implement adapters that actually call `tushare.pro_api(token).query(...)` / `akshare.*` and map the real response into the canonical contracts. Keep the existing hardcoded classes, but rename them out of the "real provider" namespace (e.g. `SyntheticFixtureTuShareAdapter`) so `provider_id` can never collide with `tushare_pro_primary`/`akshare_secondary` in a certification artifact.

### REQ-3 — Persisted, checksummed warehouse
Any dataset certified as `LOCAL_PRODUCTION_VERIFICATION_DATA` must correspond to Parquet files that actually exist on disk under `data/research/<dataset_id>/`, written by a real ingestion run and checksummed via `DatasetManifestManager`. Reserve this tag strictly for a genuine historical pull that was performed once with real credentials and cached — never for formula-generated data. In-memory-only formula generation must be tagged `SYNTHETIC_DATA`.

### REQ-4 — Cross-provider reconciliation must reconcile real sources
`run_cross_provider_reconciliation_audit` may only feed `CrossProviderReconciler` with contracts carrying `fetched_via_network=True` from two independent providers. Reconciling two synthetic adapters must be relabeled and excluded from any `REAL_PROVIDER`/production certification artifact — it may remain as a component unit test of the reconciler's arithmetic, explicitly tagged `SYNTHETIC_DATA`.

### REQ-5 — Fail-closed default
Absent a verified real fetch, every certification path defaults to `SYNTHETIC_DATA`, not `LOCAL_PRODUCTION_VERIFICATION_DATA`. `LOCAL_PRODUCTION_VERIFICATION_DATA` must never be reachable from a pure formula-generation function.

### REQ-6 — Remove silent fallbacks (F7, F8)
`warehouse_loader.py`'s empty-lookup fallback and `replay_engine.py`'s missing-artifact fallback must both raise (`FAIL CLOSED: ...`) instead of substituting fixture data. This is a direct application of the existing Fail-Closed principle (Section 20) the project already claims to enforce elsewhere.

### REQ-7 — Adversarial test: fabrication cannot be flipped on by a token alone
New test: set `TUSHARE_TOKEN` to a value that passes the preflight structural check but points at a mock HTTP server that returns clearly-synthetic canary values. Assert the certification pipeline either (a) surfaces those exact canary values with `REAL_PROVIDER` (proving the data genuinely flowed through), or (b) fails closed. It must be structurally impossible for `REAL_PROVIDER` to appear stamped on the pre-existing hardcoded literals.

---

## 4. Non-Goals

- Does not modify PIT, snapshot, revision, replay, or immutability logic — that architecture passed audit and stays as-is.
- Does not require acquiring a production `TUSHARE_TOKEN` right now — that is a business/credentialing decision outside this phase's scope. Phase 7H can close with live execution still `SKIPPED (CREDENTIALS_UNAVAILABLE)`, as long as the *mechanism* is provably incapable of mislabeling synthetic data as real.
- Does not start Phase 8 (broker/execution). That remains blocked regardless of Phase 7H's outcome.

## 5. Acceptance / Stop Condition

Phase 7H closes only when:
1. REQ-1 through REQ-6 are implemented and covered by tests.
2. REQ-7's adversarial test exists and passes.
3. A fresh audit (same method as this document's Section 2) finds zero code paths where `data_origin` can become `REAL_PROVIDER` or `LOCAL_PRODUCTION_VERIFICATION_DATA` without a corresponding real, persisted, checksummed fetch.
4. Full suite re-run and results reported honestly: expect fewer "PASS" counts than Phase 7G until real credentials are actually supplied — a lower certified number here is correct, not a regression.

🛑 Phase 8 (broker integration, live trading, any execution) remains explicitly out of scope and blocked until a CEO separately authorizes it, independent of Phase 7H's outcome.
