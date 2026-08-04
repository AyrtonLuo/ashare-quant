# Point-in-Time Research Integrity Specification (Phase 7)

## 1. Executive Principle
The fundamental premise of Phase 7 is:
$$\text{VALUE SOURCE} \neq \text{TIME TRUTH}$$

A provider can report what a metric value is, but the Point-in-Time (PIT) Layer strictly determines **when** that metric value was legally visible to a quantitative research system.

## 2. Temporal Metadata Standard
Every data contract entering research and backtesting must contain the complete temporal contract tuple:
- `event_time`: When the real-world event occurred.
- `effective_date`: The accounting/trade date described ("YYYY-MM-DD").
- `available_at`: Precise timestamp when the data was legally published and available.
- `received_at`: Timestamp when the data payload arrived in the system.
- `as_of`: Point-in-time query cutoff timestamp.

## 3. Provider-Reported Metric Policy
Provider-reported valuation and fundamental metrics (`PE`, `PE_TTM`, `PB`, `Dividend Yield`, `ROE`, `ROA`) do NOT need to be redundantly re-calculated if already provided with clear field definitions.

However, they MUST:
1. Carry `MetricProvenance.PROVIDER_REPORTED`.
2. Retain full temporal metadata (`provider`, `provider_field`, `provider_timestamp`, `event_time`, `effective_date`, `available_at`, `received_at`, `as_of`).
3. If marked `CURRENT_ONLY` or `NOT_PIT_VERIFIED`, be strictly blocked from entering past backtests ($\text{as\_of} < T$).

## 4. Current API Leak Protection
If a current API returns metric value $V_{\text{current}} = 99$, but the historical valid PIT value as of $T$ was $V_{\text{PIT}} = 10$:
- The Backtest Engine MUST receive $10$.
- If no PIT record with $\text{available\_at} \le T$ exists, the system MUST return `UNAVAILABLE` or `MISSING_PIT_DATA`.
- **PROHIBITED**: `fillna(0)`, falling back to current API values, or silent substitution.

## 5. Derived Metrics Lineage Policy
All system-computed signals, factors, and composite metrics must be tagged `MetricProvenance.DERIVED` and record:
- `input_data_ids`: Identifiers of input temporal contracts.
- `input_snapshot_id`: Snapshot ID of input state.
- `formula_version`: Version of the calculation logic.
- `calculation_timestamp`: Precise calculation time.
