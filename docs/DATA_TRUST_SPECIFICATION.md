# 🛡️ Data Trust Specification — Validation Engine & DataTrustGate

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-002`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. DataTrustGate Pipeline

```text
Raw Provider Output
        │
        ▼
┌──────────────────────────┐
│ Normalization Engine     │ -> Standardizes symbol format (600519.SH), CNY currency, floats
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Independent Calculator   │ -> Computes PE, PE-TTM, PB, Dividend Yield deterministically
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Validation Engine        │ -> High >= Low, Close > 0, Volume >= 0, PIT Disclosure check
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ DataTrustGate            │ -> Filters out INVALID/SUSPECT data
└──────────┬───────────────┘
           │
           ▼
 Canonical Data Contracts (Passed to Quant Engine)
```

---

## 2. Mandatory Data Quality Status Definitions

- `VALID`: Passed all hard validation rules, deterministic mathematical calculations, and PIT checks.
- `INVALID`: Failed hard validation (e.g. High < Low, negative volume, zero shares outstanding). Blocked from Quant Engine.
- `SUSPECT`: Divergence detected between primary and secondary feeds (e.g. > 0.5% price difference).
- `MISSING`: Data point unavailable. Flagged explicitly, **NEVER auto-filled with 0**.
- `NOT_MEANINGFUL`: Applied when mathematical precondition fails (e.g. Negative EPS -> PE = `NOT_MEANINGFUL`, Negative Book Value -> PB = `NOT_MEANINGFUL`).
