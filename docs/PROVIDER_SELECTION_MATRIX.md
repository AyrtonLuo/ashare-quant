# 🏆 Provider Selection Matrix & Tier Strategy

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-003`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Provider Tier Assignment

| Tier Level | Provider Candidate | Designated Role | Selection Rationale |
| :--- | :--- | :--- | :--- |
| **Tier 1 (Primary)** | **TuShare Pro** | Core Historical Market Data, Fundamental Statements & Corporate Actions | High API stability, token rate limits, comprehensive A-Share historical depth & PIT dates. |
| **Tier 2 (Secondary)** | **AkShare** | Real-Time Quotes, Alternative Data & Cross-Source Verification Feed | Open source, broad coverage, no rate limit token costs for real-time snapshots. |
| **Tier 3 (Research / Institutional)** | **Choice / Wind / Custom** | Institutional Validation Benchmark | Enterprise SLA, institutional corporate action precision. |

---

## 2. Failover & Drift Protection Policy

If TuShare Pro experiences an API timeout, rate-limit exception, or malformed response:
1. `TuShareAdapter` traps the error and emits `ProviderError`.
2. Provider Pipeline automatically falls back to `AkShareAdapter`.
3. Quality status is tagged `DEGRADED_FALLBACK`.
4. Quant Engine continues operating without system crash or data leakage.
