# 🎯 Data Quality Specification — Scoring & Filtering Rules

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-002`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Data Quality Score Calculation Formula

$$\text{Quality Score} = 0.4 \times S_{\text{Completeness}} + 0.3 \times S_{\text{Freshness}} + 0.3 \times S_{\text{CrossAgreement}}$$

1. **Completeness Score ($S_{\text{Completeness}}$)**: Proportion of non-missing required fields.
2. **Freshness Score ($S_{\text{Freshness}}$)**: $1.0$ if trading date is current, decreases with stale days.
3. **Cross-Source Agreement Score ($S_{\text{CrossAgreement}}$)**:
   - $1.0$ if divergence between primary and secondary feeds $< 0.1\%$.
   - $0.5$ if divergence $< 1.0\%$.
   - $0.0$ if divergence $\ge 1.0\%$.

---

## 2. Hard Quality Rule

Quality Score acts as an informational metric, but **CANNOT override `INVALID` or `SUSPECT` quality status**. Data with `INVALID` quality status is strictly blocked by `DataTrustGate`.
