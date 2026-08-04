# Research Run Specification (Phase 7B)

## 1. Overview
A Research Run represents an immutable execution of a quantitative strategy or factor experiment tied to a specific dataset snapshot.

## 2. Input & Result Manifests

### 2.1 `ResearchInputManifest`
Captures 100% of input configurations required to execute a run:
- Dataset & Snapshot Metadata
- Temporal Window (`start_date`, `end_date`, `as_of`)
- Universe Specification (`universe_symbols`, `universe_hash`)
- Factor Configurations & `factor_definition_hash`
- Strategy Parameters & `parameter_hash`
- Portfolio Constraints & `cost_model_config`
- Benchmark Metadata & `code_version`

### 2.2 `ResearchResultManifest`
Captures SHA-256 hashes of all output artifacts:
- `result_hash`
- `equity_curve_hash`
- `positions_hash` (or `"UNAVAILABLE"`)
- `trades_hash` (or `"UNAVAILABLE"`)
- `signals_hash` (or `"UNAVAILABLE"`)
- `factor_output_hash` (or `"UNAVAILABLE"`)
- `performance_metrics_hash` (or `"UNAVAILABLE"`)
- `drawdown_hash` (or `"UNAVAILABLE"`)

Missing outputs are explicitly marked `"UNAVAILABLE"`. No guessing or empty fill values are permitted.

## 3. `ResearchRunStore` Immutability
`ResearchRunStore` (`src/quant/reproducibility/store.py`) persists run manifests and metadata under:
`data/research/runs/<research_run_id>/`

Attempting to modify or overwrite an existing `research_run_id` fails closed with:
`ValueError: FAIL CLOSED: Research Run ID '<id>' already exists and is IMMUTABLE.`
