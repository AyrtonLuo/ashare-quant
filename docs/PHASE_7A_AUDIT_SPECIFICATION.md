# Phase 7A Architecture Audit Specification

## 1. Overview & Objectives
Phase 7A is an architectural audit and hardening phase designed to verify that Point-in-Time (PIT) data contracts, Snapshot immutability, Revision control, and ResearchDataAPI gating are strictly enforceable throughout `ashare-quant`.

The audit evaluates two core questions:
1. *"Can any research or backtest computation accidentally or intentionally obtain information that was not legally available at its historical as_of time?"*
2. *"Can a previously frozen research snapshot or revision lineage change after new provider data arrives?"*

## 2. Audit Framework & 14 Critical Audits

### Audit #1 — PIT Bypass Audit
Ensures all data queries route through `SnapshotManager` / `ResearchDataAPI` with mandatory `as_of` or `snapshot_id` parameters. Prohibits un-gated queries.

### Audit #2 — Current Value Leak Audit
Enforces that current-only or future available metric values (`available_at > as_of` or tagged `CURRENT_ONLY` / `NOT_PIT_VERIFIED`) are strictly blocked from entering past backtest states.

### Audit #3 — Snapshot Immutability Audit
Proves that `snapshot_id = X` represents a logically frozen state. Subsequent data ingestion, restatements, or backfilled revisions received after snapshot creation (`received_at > snapshot.created_at`) CANNOT alter snapshot query results.

### Audit #4 — Revision Immutability Audit
Verifies that revision chains ($R_A \rightarrow R_B \rightarrow R_C$) preserve full chronological history without in-place overwriting or record deletion.

### Audit #5 — Provider Metric Semantics Audit
Validates that provider-reported metrics (`PE`, `PE_TTM`, `PB`, `Dividend Yield`, `ROE`, `ROA`) preserve all temporal fields (`provider`, `provider_field`, `provider_timestamp`, `available_at`, `received_at`, `as_of`, `provenance`).

### Audit #6 — Derived Metric Temporal Lineage Audit
Verifies `DerivedDataContract` preserves `input_snapshot_id`, `input_data_ids`, `formula_version`, and `calculation_timestamp`.

### Audit #7 — Research API Enforcement Audit
Confirms that `src/quant/` code does NOT import raw provider SDKs (`tushare`, `akshare`) or direct storage adapters, routing 100% of historical data access through `ResearchDataAPI`.

### Audit #8 — Factor Temporal Integrity Audit
Audits factor implementations to ensure rolling windows only consume observations with `available_at <= as_of`.

### Audit #9 — Backtest Temporal Integrity Audit
Confirms `BacktestEngine` binds `snapshot_id` and `as_of` for every simulation run.

### Audit #10 — Survivorship Bias Audit
Audits `SecurityMasterRegistry` to ensure historical universe queries filter by `list_date`, `delist_date`, and point-in-time daily trading suspensions (`register_suspension`).

### Audit #11 — Corporate Action Temporal Integrity Audit
Ensures ex-dates, announcement dates, and split/dividend adjustments are PIT-aligned.

### Audit #12 — Data Revision vs Data Correction Audit
Validates non-destructive handling of provider restatements via `supersedes_revision_id`.

### Audit #13 — Research Run Reproducibility Audit
Validates `ResearchRunManifest` reproducibility hash matching.

### Audit #14 — Adversarial Attack Tests Audit
Executes 5 explicit bypass attack scenarios targeting PIT gating, current value leakage, snapshot corruption, missing data fillna(0), and historical universe retention.
