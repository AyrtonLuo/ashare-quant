# 🧪 Testing Architecture — Quality Assurance & Data Verification

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-001`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Testing Strategy & Pyramid

The new Quant Platform enforces a 4-tier testing strategy:

```text
               ┌──────────────────────────┐
               │ 1. Numerical Truth Tests │ -> Financial math & PIT accuracy
               └────────────┬─────────────┘
                            │
               ┌────────────┴─────────────┐
               │ 2. Contract Schema Tests │ -> Pydantic & Data Contract validation
               └────────────┬─────────────┘
                            │
               ┌────────────┴─────────────┐
               │ 3. Quant Domain Tests    │ -> Factor, Signal, Strategy, Risk logic
               └────────────┬─────────────┘
                            │
               ┌────────────┴─────────────┐
               │ 4. System & API Tests    │ -> End-to-End application flows
               └──────────────────────────┘
```

---

## 2. Test Categories & Guidelines

### Category 1: Numerical Truth Tests
- **Objective**: Verify that PE(TTM), PB, Z-scores, Returns, and Volatility match mathematical definitions exactly.
- **Rule**: Dummy data / synthetic price series with known analytical solutions must be used to test factor calculations.

### Category 2: Data Contract Schema Tests
- **Objective**: Ensure Provider Adapters emit strict `MarketDataContract` and `FundamentalDataContract` objects. Invalid types or missing timestamps must fail immediately.

### Category 3: Quant Engine Logic Tests
- **Objective**: Verify that neutralization, winsorization, portfolio rebalancing, and risk limit checks execute correctly without look-ahead bias.

---

## 3. Strict Testing Rules

- **Zero Silent Exception Swallowing**: `try...except: pass` is prohibited in test and production code.
- **No Hardcoded Dummy Data in Production**: Mock data is strictly contained inside `tests/` fixtures.
