# ⚙️ Historical Data Ingestion Specification — Pipeline, Incremental Updates & Idempotency

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-005B`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Ingestion Pipeline & Principles

```text
DATA PROVIDER (TuShare / AkShare)
       │
       ▼ RAW INGESTION
CANONICAL NORMALIZATION
       │
       ▼ TEMPORAL CLASSIFICATION
DATA TRUST GATE VALIDATION
       │
       ▼ PARQUET PARTITION STORAGE (src/data/storage/parquet_adapter.py)
DUCKDB ANALYTICAL QUERY ENGINE (src/data/storage/duckdb_adapter.py)
       │
       ▼
QUANT ENGINE & BACKTESTER
```

- **Incremental Ingestion**: New trade dates append seamlessly into symbol Parquet partitions (`test_historical_incremental_update.py`).
- **Idempotency**: Duplicate symbol-date ingestion requests perform automatic deduplication on `(symbol, trading_date)`, maintaining strict zero-duplicate rows (`test_historical_idempotency.py`).
- **Failure Recovery**: API timeouts or rate limits log errors safely without crashing the ingestion engine or filling missing bars with dummy `0` values (`test_historical_failure_recovery.py`).
