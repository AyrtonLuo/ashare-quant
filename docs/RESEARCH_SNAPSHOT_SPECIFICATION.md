# Research Snapshot & Run Linkage Specification (Phase 7)

## 1. Executive Summary
To achieve research-grade reproducibility, every quantitative experiment and backtest run must be cryptographically tied to the exact Data Snapshot world on which it was executed.

## 2. ResearchRunManifest Linkage Schema
`ResearchRunManifest` (`src/quant/reproducibility/manifest.py`) explicitly records:
- `research_run_id`: Unique identifier for the research execution.
- `snapshot_id`: ID of the `DataSnapshot` used for input data.
- `dataset_version`: Exact version of dataset (e.g. `ds_v1.0`).
- `as_of`: Cutoff timestamp specifying the data visibility cutoff.
- `strategy_config_hash`: SHA-256 hash of strategy parameters.
- `factor_config_hash`: SHA-256 hash of factor engine configuration.
- `code_version`: Version of research engine code.
- `result_hash`: SHA-256 hash of backtest equity curve and performance metrics.

## 3. Backtest Determinism Guarantee
Given:
$$\text{snapshot\_id} + \text{strategy\_config\_hash} + \text{code\_version}$$

Re-running the backtest at any point in the future MUST produce 100% identical trades, equity curves, Sharpe ratio, and total returns. Future data restatements or provider revisions created under new snapshot IDs will never alter past experiment results.

## 4. Logical Storage Architecture
Logical snapshots use a lightweight, zero-copy storage pattern:
$$\text{Immutable Parquet Datasets} + \text{RevisionStore Metadata} + \text{Snapshot Manifest Hash}$$

This eliminates data redundancy while maintaining total auditability and instant point-in-time reconstruction.
