# Live Provider Verification & Cross-Provider Certification Specification (Phase 7E)

## 1. Overview & Executive Objectives
Phase 7E specifies the production data certification, credential preflight audit, data origin classification, and cross-provider reconciliation protocols for live quantitative research platforms.

The pipeline proves the complete end-to-end certification chain:
$$\text{REAL PROVIDER} \rightarrow \text{PREFLIGHT} \rightarrow \text{LIVE API FETCH} \rightarrow \text{PROVENANCE} \rightarrow \text{DATATRUSTGATE} \rightarrow \text{CROSS-RECONCILIATION} \rightarrow \text{PARQUET/DUCKDB} \rightarrow \text{PIT SNAPSHOT} \rightarrow \text{DATASET CERTIFICATION} \rightarrow \text{RESEARCH RUN} \rightarrow \text{REPLAY} \rightarrow \text{IDENTICAL HASH}$$

## 2. Safety & Zero Secret Leakage Policy
- Provider API credentials are read strictly from environment variable `TUSHARE_TOKEN`.
- `ProviderCredentialPreflight` inspects credential availability without printing, logging, or persisting secret bytes.
- If credentials are absent, live provider tests skip gracefully (`@pytest.mark.real_provider`), final status is reported as `PASS WITH LIMITATIONS`, and `LIVE_PROVIDER_VERIFICATION` is certified as `NOT VERIFIED`.

## 3. Data Origin Certification Matrix

| Tag Name | Definition | Authorized Usage |
| :--- | :--- | :--- |
| `REAL_PROVIDER` | Direct network response from authenticated provider API. | Live network API ingestions ONLY. |
| `LOCAL_PRODUCTION_VERIFICATION_DATA` | Verified production historical dataset stored locally in Parquet. | Local production pipeline verification. |
| `GOLDEN_DATASET` | Benchmark golden fixture. | Multi-factor experiment reference testing. |
| `SYNTHETIC_DATA` | Unit test mock fixture. | Isolated component unit tests. |

Adversarial assertion: `LOCAL_PRODUCTION_VERIFICATION_DATA != REAL_PROVIDER`.

## 4. Cross-Provider Reconciliation Layer
Reconciles TuShare Pro (`tushare_pro_primary`) against AkShare (`akshare_secondary`):
- `MATCH`: Relative difference $\le 0.1\%$.
- `ACCEPTABLE_DIFFERENCE`: Relative difference $\le 1.0\%$.
- `MATERIAL_DIFFERENCE`: Relative difference $> 1.0\%$ (flagged for review, zero silent overwrites).
- `PROVIDER_UNAVAILABLE`: One or both providers unavailable.
