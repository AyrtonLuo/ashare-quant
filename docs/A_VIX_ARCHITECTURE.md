# 📈 A-VIX Architecture — A-Share Volatility Indicator Specification

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-001`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Executive Definition & Purpose

The **A-Share Volatility Index (A-VIX)** is a proprietary composite quantitative volatility indicator designed to measure market stress, downside tail risk, and expected volatility across China A-Share benchmark indices (CSI 300 / SSE 50).

---

## 2. Mathematical Definition & Data Methodology

A-VIX combines two distinct volatility methodologies:

### Methodology A: Realized Volatility Composite (20-Day & 60-Day)
$$\sigma_{\text{Realized}} = \sqrt{\frac{252}{N-1} \sum_{i=1}^{N} \left( r_i - \bar{r} \right)^2} \times 100$$
- **Inputs**: Log returns of CSI 300 index (`000300.SH`) and SSE 50 index (`000016.SH`).

### Methodology B: Implied Volatility Surface (CSI 300 Index Options / 50ETF Options)
$$VIX_{\text{Implied}} = 100 \times \sqrt{\frac{2}{T} \sum_i \frac{\Delta K_i}{K_i^2} e^{R \cdot T} Q(K_i) - \frac{1}{T} \left( \frac{F}{K_0} - 1 \right)^2}$$
- **Inputs**: Near-term and next-term out-of-the-money put and call option quotes on SSE 50 ETF Options (`510050.SH`) and CSI 300 ETF Options (`510300.SH`).

---

## 3. Disclaimers & Data Limitations

1. **Realized Volatility $\ne$ Implied Volatility**: Realized volatility measures past price dispersion; implied volatility measures option market forward pricing.
2. **Options Liquidity Constraint**: A-Share options markets may experience illiquidity during extreme trading halts; when options data is unavailable, A-VIX automatically falls back to GARCH(1,1) Realized Volatility Composite and marks `status = REALIZED_FALLBACK`.
