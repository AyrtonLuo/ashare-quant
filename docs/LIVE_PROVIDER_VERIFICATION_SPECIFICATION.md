# Live Provider Verification Specification (Phase 7D)

## 1. Overview & Objectives
Phase 7D defines the Live Provider Credentialed Verification protocol for live network data feeds.

The purpose of Phase 7D is certifying the live API provenance chain:
$$\text{REAL PROVIDER API} \rightarrow \text{REAL API RESPONSE} \rightarrow \text{PROVIDER ADAPTER} \rightarrow \text{CANONICAL NORMALIZATION} \rightarrow \text{DATATRUSTGATE} \rightarrow \text{PARQUET} \rightarrow \text{DUCKDB} \rightarrow \text{PIT SNAPSHOT} \rightarrow \text{DATASET LOCK} \rightarrow \text{RESEARCH RUN} \rightarrow \text{REPLAY} \rightarrow \text{IDENTICAL HASH}$$

## 2. Safety & Zero Secret Leakage Policy
- Live API tokens are read strictly from environment variable `TUSHARE_TOKEN`.
- Hardcoding credentials in source code, unit tests, log files, dataset manifests, or exception tracebacks is strictly prohibited.
- `ProviderCredentialPreflight` inspects credential status without logging or exposing secret bytes.

## 3. Pre-Flight Credential Audit Matrix

| Preflight Status | System Action | Audit Result Tag |
| :--- | :--- | :--- |
| `AVAILABLE` | Execute live API queries over 5 symbols (`600519.SH`, `000858.SZ`, `000001.SZ`, `300750.SZ`, `688981.SH`). | `VERIFIED_LIVE_PROVIDER` |
| `UNAVAILABLE` | Skip `@pytest.mark.real_provider` tests. Report status `PASS WITH LIMITATIONS`. | `LIVE_PROVIDER_VERIFICATION = NOT VERIFIED` |
| `INVALID` | Skip live tests. Report credential error safely. | `LIVE_PROVIDER_VERIFICATION = NOT VERIFIED` |
| `API_UNREACHABLE` | Skip live tests. Report network/connectivity probe failure. | `LIVE_PROVIDER_VERIFICATION = NOT VERIFIED` |

## 4. Real Data Origin Tagging
Datasets, manifests, and canonical contracts explicitly record `data_origin`:
- `REAL_PROVIDER`: Real network API responses.
- `LOCAL_PRODUCTION_VERIFICATION_DATA`: Local production verification datasets.
- `GOLDEN_DATASET`: Immutable golden dataset fixtures.
- `SYNTHETIC_DATA`: Synthetic unit test data.
