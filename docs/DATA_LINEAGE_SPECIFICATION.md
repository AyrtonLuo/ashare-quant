# 🔍 Data Lineage Specification — Provenance Metadata Architecture

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-002`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Data Lineage Metadata Fields

Every record served by the Data Trust Layer carries mandatory lineage attributes:
- `symbol`: Security identifier (e.g. `600519.SH`)
- `field_name`: Field identifier (e.g. `pe_ttm`)
- `observed_value`: Calculated value
- `provider_primary`: Primary provider adapter (e.g. `akshare_primary`)
- `endpoint_name`: Specific API endpoint name
- `retrieved_at`: UTC ISO timestamp when data was fetched
- `trade_date`: Associated market trading date
- `report_date`: Associated financial statement period
- `announcement_date`: PIT publication disclosure date
- `calculation_version`: Version of `FinancialMetricsCalculator`
- `verification_status`: `VERIFIED` / `SUSPECT` / `UNVERIFIED`
- `quality_score`: Numeric confidence rating from `0.0` to `1.0`.
