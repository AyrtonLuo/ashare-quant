# 📊 Data Provider Validation Matrix — AkShare vs TuShare vs Choice

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-002`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. 18-Field Data Provider Field Validation Matrix

| Data Field | AkShare (Primary) | TuShare Pro (Secondary) | Choice / Wind (Institutional) | Validation Result / Status | Recommended Primary Feed |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Historical Price (Daily OHLC)** | Validated | Validated | Verified | **PASS (Consistent)** | AkShare |
| **Real-Time / Delayed Price** | Validated | Validated | Verified | **PASS (Consistent)** | AkShare |
| **Volume & Amount** | Validated | Validated | Verified | **PASS (Consistent)** | AkShare |
| **Turnover Rate** | Calculated | Calculated | Native | **PASS (Verified via Float Shares)** | Independent Calc |
| **Market Cap & Total Shares** | Validated | Validated | Verified | **PASS (Consistent)** | TuShare / AkShare |
| **Shares Outstanding (Float)** | Verified | Verified | Verified | **PASS (Consistent)** | TuShare |
| **EPS (Annual Reported)** | Verified | Verified | Verified | **PASS (Consistent)** | AkShare |
| **EPS (TTM Trailing 4Q)** | Needs Verification | Needs Verification | Native | **REJECTED DIRECT / USE INDEPENDENT CALC** | Independent Calc |
| **Revenue & Growth** | Validated | Validated | Verified | **PASS (Consistent)** | AkShare |
| **Net Income** | Validated | Validated | Verified | **PASS (Consistent)** | AkShare |
| **PE (Static / LYR)** | Mismatch Risk | Mismatch Risk | Native | **REJECTED DIRECT / USE INDEPENDENT CALC** | Independent Calc |
| **PE (TTM)** | **HIGH MISMATCH** | **HIGH MISMATCH** | Native | **REJECTED DIRECT / USE INDEPENDENT CALC** | Independent Calc |
| **PB (Price-to-Book)** | Mismatch Risk | Mismatch Risk | Native | **REJECTED DIRECT / USE INDEPENDENT CALC** | Independent Calc |
| **Dividend Cash Amount** | Validated | Validated | Verified | **PASS (Consistent)** | AkShare / TuShare |
| **Dividend Yield (TTM)** | Discrepancies | Discrepancies | Native | **REJECTED DIRECT / USE INDEPENDENT CALC** | Independent Calc |
| **ROE / ROIC** | Validated | Validated | Verified | **PASS (Consistent)** | AkShare |
| **Corporate Actions (Dividends/Splits)**| Validated | Validated | Verified | **PASS (Consistent)** | AkShare |
| **Trading Calendar & Suspensions** | Validated | Validated | Verified | **PASS (Consistent)** | AkShare |

---

## 2. Key Findings & Rejected Provider Fields

1. **Rejection of Third-Party Direct PE/PE-TTM/PB/Dividend Yield**:
   - Provider direct metrics (e.g. AkShare/TuShare direct `pe_ttm` columns) exhibit definition mismatch, negative EPS handling discrepancies, and ex-rights timing lag.
   - **Decision**: All valuation metrics (PE, PE-TTM, PB, Dividend Yield) **MUST BE CALCULATED INDEPENDENTLY** by `FinancialMetricsCalculator` using validated raw price and financial statement components. Direct provider valuation values are strictly rejected.
