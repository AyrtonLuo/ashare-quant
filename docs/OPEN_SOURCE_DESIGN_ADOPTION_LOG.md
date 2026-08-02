# 📓 Open-Source Design Adoption Log

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-005A`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Architectural Adoption Tracking

| Source Project | Architectural Concept | Why Useful | How Adapted in AI Quant Pro | Why Not Copied Directly |
| :--- | :--- | :--- | :--- | :--- |
| **Microsoft Qlib** | Dataset Manifest & Feature Processor Pipeline | Ensures 100% reproducible historical datasets and standardized Z-scores | Implemented `DatasetManifest` with SHA-256 checksums and explicit column schemas | Qlib uses opaque binary files (`$close`), whereas we use DuckDB + Parquet contracts for full auditability. |
| **Zipline** | Point-in-Time Data Bundle & Available_At Gating | Eliminates look-ahead bias by separating disclosure date from fiscal period | Enforced `available_at <= query_as_of` in `PITGate` and `FundamentalDataContract` | Zipline's bcolz storage format is deprecated; we use native Parquet columnar tables. |
| **QuantConnect (LEAN)** | Canonical Security Master & Delisting Lifecycle | Prevents survivorship bias by keeping historical prices for delisted securities | Implemented `SecurityMasterRegistry` with point-in-time tradability checks | LEAN is C#-based; we build native Python dataclass interfaces. |
| **Backtrader** | Slippage & Stamp Duty Transaction Cost Models | Accurately models A-Share transaction costs in backtesting | Adopted `0.05%` sell-side stamp duty and `0.025%` commission rules | Backtrader's line-based iteration is slow; we build vectorized array engines. |
