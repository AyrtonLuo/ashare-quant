# 📐 Factor Engine Specification — Calculation, Winsorization & Z-Score Normalization

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006A`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Implemented Factors

1. **Price Momentum (`PriceMomentumFactor`)**: $20\text{D}, 60\text{D}, 120\text{D}$ cumulative price return:
   $$\text{Momentum}_N = \frac{P_t - P_{t-N}}{P_{t-N}}$$
2. **Realized Volatility (`RealizedVolatilityFactor`)**: Annualized volatility over trailing $N$ trading days:
   $$\text{Volatility}_N = \sigma(\text{Daily Returns}) \times \sqrt{252}$$
3. **Average Volume (`AverageVolumeFactor`)**: $20\text{D}$ average trading volume.
4. **Valuation Adapter (`ValuationFactorAdapter`)**: Adapts PE, PB, and Dividend Yield with explicit `MetricProvenance` (`PROVIDER_REPORTED` or `SYSTEM_CALCULATED`).

---

## 2. Factor Normalization Pipeline (`FactorNormalizer`)

```text
Raw Factor Value
       │
       ▼ Validity Check (Status = VALID)
3-Sigma Winsorization Clipping (lower = mean - 3*std, upper = mean + 3*std)
       │
       ▼
Cross-Sectional Z-Score Standardization (z = (x - mean) / std)
       │
       ▼
Normalized Factor Score
```
