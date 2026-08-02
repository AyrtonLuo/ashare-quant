# 💾 Historical Data Storage Specification — Parquet & DuckDB Architecture

**Document Version**: 2.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-005B`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Storage Architecture & Layering

Large historical binary datasets are stored outside Git version control. The storage architecture is partitioned into 5 logical tiers:

```text
data/
├── raw/            # Raw JSON / CSV provider payload snapshots (Git Ignored)
├── normalized/     # Schema-normalized daily bar and statement tables (Git Ignored)
├── validated/      # Point-in-time verified data (Passed DataTrustGate) (Git Ignored)
├── research/       # Production Apache Parquet symbol partitions (Git Ignored)
└── manifests/      # SHA-256 DatasetManifest JSON provenance files (Git Tracked)
```

---

## 2. Production Storage Implementation (Parquet + DuckDB)

- **Parquet Storage Adapter**: Implemented in `src/data/storage/parquet_adapter.py` (`ParquetStorageAdapter`). Performs columnar writes and symbol-date deduplicated reads.
- **DuckDB Analytical Query Engine**: Implemented in `src/data/storage/duckdb_adapter.py` (`DuckDBQueryEngine`). Executes high-speed in-memory OLAP SQL queries directly over Parquet partitions (`read_parquet`).

---

## 3. Git Version Control Policy

- `data/raw/`, `data/normalized/`, `data/validated/`, `data/research/`, `*.parquet`, and `*.db` are strictly excluded in `.gitignore`.
- Git tracks only: Source code, `DatasetManifest` provenance files (`data/manifests/`), Golden Dataset fixtures (`tests/data/golden/`), Data Contracts, and Storage Adapters.
