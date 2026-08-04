# Real Provider Provenance Specification (Phase 7E)

## 1. Overview
The Real Provider Provenance Specification defines field-level metadata requirements to guarantee that every data record ingested from live APIs retains 100% auditable origin information.

## 2. Required Provenance Fields
Every canonical record ingested from live providers must carry:
- `provider`: Unique provider string (`"tushare_pro_primary"` or `"akshare_secondary"`).
- `provider_field`: Raw provider field name (e.g. `"close"`, `"pe_ttm"`).
- `provider_timestamp`: Timestamp issued by the provider.
- `event_time`: Time when the historical event occurred.
- `effective_date`: Trading date associated with the data.
- `available_at`: Time when the data legally became available for trading.
- `received_at`: System ingestion timestamp.
- `data_origin`: Origin tag (`"REAL_PROVIDER"` or `"LOCAL_PRODUCTION_VERIFICATION_DATA"`).

## 3. Auditing Provenance Integrity
During data ingestion, `DataTrustGate` validates that all required provenance fields are populated. If provenance metadata is missing or corrupted, the record is rejected immediately (`quality_status = INVALID`).
