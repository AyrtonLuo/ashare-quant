# ⚙️ Provider Operation Specification — Rate Limits & Health Monitoring

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-004`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Rate Limiting & Failover Protocol

1. **TuShare Pro Rate Limits**: Max 200 calls/minute for standard tier; `TuShareAdapter` enforces 10s default timeout.
2. **Health Monitoring**: `ProviderHealthManager` tracks API errors; if 5 consecutive errors occur, failover to `AkShareProviderAdapter` is triggered.
3. **Safe Failure Policy**: API timeouts or rate limits emit `ProviderError` and return `None` with `quality_status = UNAVAILABLE`. Dummy `0` data is strictly forbidden.
