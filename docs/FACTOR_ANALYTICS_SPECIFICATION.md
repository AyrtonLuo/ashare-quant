# 📊 Factor Analytics Specification — Exposure, Correlation & Rank IC Framework

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006B`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Analytics Framework (`FactorAnalytics`)

1. **Portfolio Factor Exposure**:
   $$\text{Exposure} = \sum_{i=1}^{N} w_i \cdot Z_i$$
2. **Pearson Factor Correlation Matrix**: Computes pairwise correlation coefficients across factors to identify collinearity.
3. **Rank Information Coefficient (Rank IC)**: Spearman rank correlation between factor score at $T$ and forward asset returns:
   $$\text{Rank IC} = \text{SpearmanCorr}(\text{Factor}_T, \text{Return}_{T+k})$$
4. **IC Decay**: Calculates Rank IC across 1D, 5D, 10D, 20D, and 60D forward return horizons to evaluate signal durability.
