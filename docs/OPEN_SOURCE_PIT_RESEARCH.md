# Open-Source Quantitative PIT & Snapshot Research Log (Phase 7 / Phase 7C)

## 1. Referenced Open-Source Frameworks
We surveyed leading quantitative data and backtesting platforms to analyze their approach to Point-in-Time integrity, revision management, and reproducibility:
1. **Microsoft Qlib**: Feature store, dataset versioning, expression engine.
2. **Zipline / Zipline-Reloaded**: Point-in-time daily / minute data bundles, split/dividend adjustment handlers.
3. **QuantConnect LEAN**: Data providers, slice-based data handlers, map files for symbol changes and corporate actions.
4. **Backtrader**: Generic data feeds, line buffers.
5. **vn.py**: Event-driven trading framework, database adapters.

## 2. Adopted Concepts & Rationale

| Concept | Source Project | Implementation in ashare-quant | Rationale |
| :--- | :--- | :--- | :--- |
| **Point-in-Time Data Cutoff** | QuantConnect LEAN & Zipline | `PITGate` & `DataSnapshot.as_of` | Eliminates look-ahead bias by strictly filtering $\text{available\_at} \le T$. |
| **Dataset Versioning & Hash Manifests** | Qlib | `DatasetManifest` & `SnapshotManifest` | Guarantees 100% deterministic reproducibility for research runs. |
| **Immutable Revision History** | Enterprise Data Engineering Best Practices | `DataRevision` & `RevisionStore` | Prevents data restatements from overwriting past backtest states. |
| **Provider Metric Provenance** | QuantConnect LEAN | `MetricProvenance.PROVIDER_REPORTED` | Avoids redundant metric recalculation while maintaining temporal truth. |

## 3. Rejected Concepts & Rationale

| Concept | Source Project | Reason for Rejection |
| :--- | :--- | :--- |
| **Monolithic Binary Custom Storage** | Qlib (custom bin format) | Harder to query and audit. Adopted Parquet + DuckDB + RevisionStore metadata instead. |
| **Complex Event Sourcing Engine** | Enterprise Frameworks | Over-engineered for research engine scope. Simple `RevisionStore` + `SnapshotManager` handles PIT semantics deterministically without event bus complexity. |
| **In-Place Database Mutability** | Generic DB adapters (vn.py / Backtrader) | In-place updates corrupt historical backtest integrity. |
| **Un-PIT Provider API Direct Calls** | Direct SDK feeds | Bypassing temporal gating introduces severe look-ahead leaks. |

## 4. Phase 7C Production-Scale Dataset Verification
Phase 7C establishes production-scale verification over real A-Share market datasets (`RealDataVerificationEngine`), proving end-to-end dataset ingestion, quality auditing, snapshot isolation, and deterministic replay verification (`ReplayStatus.REPRODUCIBLE`).
