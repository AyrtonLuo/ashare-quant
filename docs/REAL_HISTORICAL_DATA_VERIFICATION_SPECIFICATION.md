# Real Historical Data Verification Specification (Phase 7C / Phase 7D)

## 1. Overview & Objectives
Phase 7C and Phase 7D establish a production-scale verification pipeline for real A-Share market datasets and live API data feeds.

The pipeline proves the complete end-to-end chain:
$$\text{REAL MARKET DATA} \rightarrow \text{CANONICAL INGESTION} \rightarrow \text{PARQUET/DUCKDB} \rightarrow \text{PIT SNAPSHOT} \rightarrow \text{DATASET LOCK} \rightarrow \text{RESEARCH RUN} \rightarrow \text{REPLAY ENGINE} \rightarrow \text{IDENTICAL SHA-256 HASH}$$

## 2. Real Data Scope & Minimum Coverage
Production verification requires at least **20 representative A-Share symbols** covering 7 core market segments:
1. **Large Cap Consumer**: `600519.SH` (Kweichow Moutai)
2. **Large Cap Financial**: `600036.SH` (China Merchants Bank)
3. **Consumer**: `000858.SZ` (Wuliangye)
4. **Growth**: `300750.SZ` (CATL)
5. **ChiNext**: `300059.SZ` (East Money)
6. **STAR Market**: `688981.SH` (SMIC)
7. **Historical Delisted/Suspended Symbols**: `000003.SZ` (PT 水仙), `600000.SH` (SPD Bank)

## 3. Data Flow & Provenance Architecture
```
TuShare Pro / AkShare APIs
         ↓
DataTrustGate Normalization
         ↓
Parquet Storage Adapter
         ↓
DuckDB Query Engine
         ↓
Historical Data Warehouse
         ↓
ResearchDataAPI (Point-in-Time Gated)
```

## 4. Credential Pre-Flight Audit & Anti-Fabrication Policy
- Live API tokens are inspected via `ProviderCredentialPreflight` from environment variable `TUSHARE_TOKEN`. Zero tokens are logged or committed.
- If credentials are available, live network tests execute over real API endpoints.
- If credentials are unavailable, live provider tests are marked `SKIPPED`, status is recorded as `PASS WITH LIMITATIONS`, and local production dataset verification is maintained without fabricating fake tokens or synthetic API responses.
