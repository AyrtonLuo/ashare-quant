# 🌐 Data Provider Architecture — Provider Isolation & Replaceability

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-003`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Provider Isolation Principle

The **Data Provider Architecture** guarantees complete isolation between external third-party APIs (TuShare, AkShare, Choice, Wind) and the Quant/Application Engine.

```text
               ┌───────────────────────┐       ┌───────────────────────┐
               │ TuShare Pro Data API  │       │ AkShare Open Source   │
               └───────────┬───────────┘       └───────────┬───────────┘
                           │                               │
                           ▼                               ▼
               ┌───────────────────────┐       ┌───────────────────────┐
               │ TuShareAdapter        │       │ AkShareAdapter        │
               └───────────┬───────────┘       └───────────┬───────────┘
                           │                               │
                           └───────────────┬───────────────┘
                                           │ Maps Raw API to Canonical Contracts
                                           ▼
                               ┌───────────────────────┐
                               │ Canonical Normalizer  │
                               └───────────┬───────────┘
                                           │
                                           ▼
                               ┌───────────────────────┐
                               │ DataTrustGate         │
                               └───────────┬───────────┘
                                           │
                                           ▼
                               ┌───────────────────────┐
                               │ Quant Engine & AI     │
                               └───────────────────────┘
```

---

## 2. Zero Leakage Rule

- **STRICT DIRECTIVE**: `import tushare` or `import akshare` is **STRICTLY PROHIBITED** outside `src/data/providers/`.
- Quant Engine, Strategy Engine, Risk Engine, AI Layer, and Web UI interact **ONLY** with `Canonical Data Contracts` (`MarketDataContract`, `FundamentalDataContract`, `SecurityMasterContract`).
- **Provider Swap Principle**: Replacing TuShare with AkShare or a future commercial feed requires modifying **ONLY** the Provider Adapter class (`src/data/providers/`). The rest of the platform remains 100% untouched.
