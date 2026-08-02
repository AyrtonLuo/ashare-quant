# 💾 Historical Data Storage Specification — Parquet & DuckDB Architecture

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-005A`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Storage Architecture & Layering

Large historical binary datasets are stored outside Git version control. The storage architecture is partitioned into 4 logical tiers:

```text
data/
├── raw/            # Raw JSON / CSV provider payload snapshots
├── normalized/     # Schema-normalized daily bar and statement tables
├── validated/      # Point-in-time verified data (Passed DataTrustGate)
└── research/       # Optimized Parquet / DuckDB columnar datasets for Quant Engine
```

---

## 2. Format Evaluation & Decision: Apache Parquet + DuckDB

| Evaluated Format | Read Scan Speed | Columnar Querying | Compression Ratio | Schema Versioning | Python Ecosystem Support | Final Decision |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Apache Parquet** | **Ultra Fast** | **Native Columnar** | **High (Snappy/GZIP)** | **Strong (PyArrow)** | **Native** | **SELECTED FOR PRODUCTION** |
| **DuckDB** | **Ultra Fast** | **Native SQL OLAP** | **High** | **Strong** | **Native** | **SELECTED FOR ANALYTICS** |
| **CSV** | Slow | No (Row-based) | Low (Plain Text) | Weak | Universal | REJECTED FOR LARGE DATA |
| **SQLite** | Medium | No (Row-based) | Medium | Moderate | Native | REJECTED FOR OLAP SCANS |

---

## 3. Git Version Control Policy

- Large `.parquet` or `.db` files are strictly added to `.gitignore`.
- Git tracks only: `DatasetManifest` files (`manifest.json`), Golden Dataset fixtures (`tests/data/golden/`), Data Contracts, and Storage Adapters.
