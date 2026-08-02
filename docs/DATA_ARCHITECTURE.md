# 📊 Data Architecture — Data Trust Layer & Lineage

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-001`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. The Data Trust Problem & Solution

### The Core Problem
Financial market data providers often contain discrepancies in PE(TTM), PB, EPS, Dividend Yield, and price adjustments (ex-rights / ex-dividend). Raw provider data cannot be blindly trusted in institutional quant engines.

### The Solution: Data Trust Pipeline
```text
Raw API Data
     │
     ▼
┌──────────────────────────┐
│ Provider Adapter         │ -> Maps raw JSON/DataFrame to Provider Interface
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Normalization Engine     │ -> Standardizes Symbols (000001.SZ), Currencies (CNY), Units
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Validation Engine        │ -> Range checks, missing value checks, timestamp checks
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Cross-Source Verifier    │ -> Compares primary vs secondary provider feeds
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Corporate Action Handler │ -> Applies Split/Dividend Adjustments (Backward/Forward)
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Canonical Data Store     │ -> Emits immutable, audit-ready Data Contracts
└──────────────────────────┘
```

---

## 2. Fundamental Metrics Definitions & Data Formulas

To guarantee zero ambiguity across the system, all fundamental metrics must follow unified mathematical definitions:

### 1. Price-to-Earnings Ratio (PE & PE-TTM)
$$\text{PE} = \frac{P}{\text{EPS}_{\text{Annual}}}$$
$$\text{PE}_{\text{TTM}} = \frac{P}{\sum_{i=1}^{4} \text{EPS}_{Q_i}}$$
- **Rule**: If $\text{EPS} \le 0$, $\text{PE}$ is set to `NaN` with `quality_status = NEGATIVE_EARNINGS`. It is NEVER filled with `0` or arbitrary negative multipliers.

### 2. Price-to-Book Ratio (PB)
$$\text{PB} = \frac{P}{\text{Book Value Per Share}}$$
- **Rule**: Book Value Per Share = $\frac{\text{Total Equity} - \text{Preferred Stock}}{\text{Shares Outstanding}}$.

### 3. Dividend Yield
$$\text{Dividend Yield} = \frac{\sum \text{Dividends Paid in Trailing 12 Months}}{P}$$

---

## 3. Data Lineage Tracking Specification

Every data point served to the Quant Engine or Web UI carries a mandatory `DataLineage` metadata block:

```json
{
  "symbol": "600519.SH",
  "metric": "pe_ttm",
  "value": 28.45,
  "lineage": {
    "provider_primary": "akshare_eastmoney",
    "provider_secondary": "tushare_pro",
    "timestamp_fetch": "2026-08-01T15:00:00Z",
    "trading_date": "2026-08-01",
    "price_used": 1650.00,
    "price_timestamp": "2026-08-01T15:00:00Z",
    "eps_trailing_sum": 58.00,
    "quarters_included": ["2025Q3", "2025Q4", "2026Q1", "2026Q2"],
    "adjustment_method": "backward_adjusted",
    "validation_status": "VERIFIED",
    "quality_score": 0.99
  }
}
```

---

## 4. Quality Status Classifications

1. `VERIFIED`: Data passed all validation checks and cross-source verification.
2. `SUSPECT`: Minor divergence detected between providers (e.g. < 0.5% price difference).
3. `INVALID`: Failed hard validation (e.g. High < Low, negative volume, stale price > 5 days).
4. `MISSING`: Data unavailable from provider; flagged explicitly, not auto-filled with 0.
5. `STALE`: Market data timestamp is older than current trading calendar window.
