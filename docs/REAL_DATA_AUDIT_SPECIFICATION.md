# Real Data Audit Specification (Phase 7C)

## 1. Quality Audit Requirements
Every production historical dataset undergo 10 audit checks before snapshot creation:

1. **Schema Validation**: Verify all required market data fields (`symbol`, `trading_date`, `open`, `high`, `low`, `close`, `volume`, `amount`).
2. **Null Validation**: Zero null values allowed in critical price/volume/date fields.
3. **Duplicate Check**: Zero duplicate `(symbol, trading_date)` records.
4. **Trading Calendar Validation**: Dates must align with A-Share SSE/SZSE trading calendars.
5. **Price Sanity**: Prices must be strictly positive ($> 0.0$).
6. **Volume Sanity**: Volume must be non-negative ($\ge 0.0$).
7. **Date Continuity Check**: No unexplained date gaps outside weekends/holidays.
8. **Corporate Action Consistency**: Ex-dates and adjustment factors must align with split/dividend records.
9. **Provider Provenance Check**: All records must specify `provider`, `available_at`, and `received_at`.
10. **Temporal Metadata Check**: `available_at <= as_of` enforced for every observation.

## 2. Audit Report Artifacts
Audit results are persisted to `data/research/audit/real_data_verification/`:
- `quality_report.json`
- `pit_report.json`
- `performance_report.json`
- `replay_report.json`
