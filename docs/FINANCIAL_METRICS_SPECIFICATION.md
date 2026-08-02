# 📐 Financial Metrics Specification — Unified Math & Handling Rules

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-002`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Valuation & Fundamental Metrics Formulas

### 1. Static Price-to-Earnings Ratio (PE / PE-LYR)
$$\text{PE}_{\text{LYR}} = \frac{P}{\text{EPS}_{\text{Annual}}}$$
- **Precondition**: $\text{EPS}_{\text{Annual}} > 0$.
- **Negative EPS Policy**: If $\text{EPS} \le 0$, return `pe = null`, `status = "NOT_MEANINGFUL"`.

### 2. Trailing Twelve Months Price-to-Earnings Ratio (PE-TTM)
$$\text{EPS}_{\text{TTM}} = \sum_{i=1}^{4} \text{EPS}_{Q_i}$$
$$\text{PE}_{\text{TTM}} = \frac{P}{\text{EPS}_{\text{TTM}}}$$
- **Precondition**: Trailing 4 quarters must all be available and $\text{EPS}_{\text{TTM}} > 0$.
- **Negative TTM Policy**: If $\text{EPS}_{\text{TTM}} \le 0$, return `pe_ttm = null`, `status = "NOT_MEANINGFUL"`.

### 3. Price-to-Book Ratio (PB)
$$\text{PB} = \frac{P}{\text{Book Value Per Share}}$$
- **Precondition**: $\text{Book Value Per Share} > 0$.
- **Negative Equity Policy**: Return `pb = null`, `status = "NOT_MEANINGFUL"`.

### 4. Dividend Yield (Trailing 12-Month)
$$\text{Dividend Yield}_{\text{TTM}} = \frac{\sum \text{Cash Dividend Per Share Paid in Past 12 Months}}{P} \times 100\%$$
- **Zero Dividend Policy**: If no cash dividends were paid in past 12 months, return `dividend_yield_ttm = 0.0`, `status = "VALID"`.
